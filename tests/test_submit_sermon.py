"""Tests for /submit_sermon: a new GUID is queued, an errored job is requeued
in place on resubmit, and a pending or completed job still answers 409."""

import os
import sqlite3
import sys
import uuid

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import app as app_module  # noqa: E402
import worker as worker_module  # noqa: E402


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "jobs_test.db")
    monkeypatch.setattr(app_module, "DATABASE", db_path)
    monkeypatch.setattr(worker_module, "DATABASE", db_path)
    app_module.init_db()
    return db_path


@pytest.fixture
def client(temp_db):
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as client:
        yield client


def _row(temp_db, guid):
    conn = sqlite3.connect(temp_db)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM sermons WHERE sermon_guid = ?", (guid,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _set(temp_db, guid, **columns):
    sets = ", ".join(f"{k} = ?" for k in columns)
    conn = sqlite3.connect(temp_db)
    conn.execute(f"UPDATE sermons SET {sets} WHERE sermon_guid = ?", (*columns.values(), guid))
    conn.commit()
    conn.close()


def test_a_new_sermon_is_queued(client, temp_db):
    guid = str(uuid.uuid4())
    resp = client.post("/submit_sermon", json={"sermon_guid": guid, "transcription": "Text"})
    assert resp.status_code == 201
    assert _row(temp_db, guid)[0]["status"] == "pending"


def test_an_errored_sermon_is_requeued_in_place(client, temp_db):
    guid = str(uuid.uuid4())
    client.post("/submit_sermon", json={"sermon_guid": guid, "transcription": "Old"})
    _set(temp_db, guid, status="error", updated_at="2026-11-17 10:00:00",
         ai_summary="partial", topics="x")

    resp = client.post("/submit_sermon", json={"sermon_guid": guid, "transcription": "New"})

    assert resp.status_code == 201
    rows = _row(temp_db, guid)
    assert len(rows) == 1
    row = rows[0]
    assert row["status"] == "pending"
    assert row["transcription"] == "New"
    assert row["updated_at"] is None
    assert row["ai_summary"] is None
    assert row["topics"] is None


@pytest.mark.parametrize("status", ["pending", "completed"])
def test_a_pending_or_completed_sermon_is_still_409(client, temp_db, status):
    guid = str(uuid.uuid4())
    client.post("/submit_sermon", json={"sermon_guid": guid, "transcription": "Old"})
    _set(temp_db, guid, status=status, ai_summary="kept")

    resp = client.post("/submit_sermon", json={"sermon_guid": guid, "transcription": "New"})

    assert resp.status_code == 409
    row = _row(temp_db, guid)[0]
    assert row["status"] == status
    assert row["transcription"] == "Old"
    assert row["ai_summary"] == "kept"


def test_missing_fields_are_still_400(client):
    assert client.post("/submit_sermon", json={"sermon_guid": str(uuid.uuid4())}).status_code == 400


@pytest.mark.parametrize("route, payload", [
    ("/submit_chapters", {"timings": [{"start": 0.0, "end": 1.0, "text": "Hi"}]}),
    ("/submit_embeddings", {"texts": {"en": "Hello world."}}),
])
def test_chapters_and_embeddings_requeue_an_errored_job(client, temp_db, route, payload):
    """The orchestrator's retry relies on these being upserts."""
    guid = str(uuid.uuid4())
    table = "chapters" if "chapters" in route else "embeddings"
    assert client.post(route, json={"sermon_guid": guid, **payload}).status_code == 201
    conn = sqlite3.connect(temp_db)
    conn.execute(f"UPDATE {table} SET status = 'error', updated_at = '2026-11-17 10:00:00' "
                 "WHERE sermon_guid = ?", (guid,))
    conn.commit()

    assert client.post(route, json={"sermon_guid": guid, **payload}).status_code == 201

    status = conn.execute(f"SELECT status FROM {table} WHERE sermon_guid = ?", (guid,)).fetchone()[0]
    conn.close()
    assert status == "pending"
