"""Tests for the embeddings job: /submit_embeddings + /embeddings_status routes
and the worker's per-cycle processing (process_embedding_jobs via the extracted
_process_embedding_cycle), with the actual Ollama call mocked.

Mirrors the chapters job's shape. Each test gets an isolated temp SQLite DB by
pointing both app.DATABASE and worker.DATABASE at a tmp file and running the
app's init_db() to create the schema.
"""

import json
import os
import sqlite3
import sys
import uuid

import pytest

# Ensure the project root imports when run from anywhere.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import app as app_module  # noqa: E402
import worker as worker_module  # noqa: E402


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Point both the Flask app and the worker at a fresh temp DB, schema created."""
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


def _db(temp_db):
    conn = sqlite3.connect(temp_db)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# /submit_embeddings route validation
# ---------------------------------------------------------------------------

def test_submit_embeddings_valid(client, temp_db):
    guid = str(uuid.uuid4())
    resp = client.post(
        "/submit_embeddings",
        json={"sermon_guid": guid, "texts": {"en": "Hello world.", "es": "Hola mundo."}},
    )
    assert resp.status_code == 201, resp.get_data(as_text=True)

    conn = _db(temp_db)
    row = conn.execute("SELECT * FROM embeddings WHERE sermon_guid = ?", (guid,)).fetchone()
    conn.close()
    assert row is not None
    assert row["status"] == "pending"
    assert json.loads(row["payload_json"]) == {"en": "Hello world.", "es": "Hola mundo."}
    assert row["result_json"] is None


def test_submit_embeddings_one_language_ok(client, temp_db):
    guid = str(uuid.uuid4())
    resp = client.post(
        "/submit_embeddings",
        json={"sermon_guid": guid, "texts": {"en": "English only."}},
    )
    assert resp.status_code == 201
    conn = _db(temp_db)
    row = conn.execute("SELECT payload_json FROM embeddings WHERE sermon_guid = ?", (guid,)).fetchone()
    conn.close()
    assert json.loads(row["payload_json"]) == {"en": "English only."}


def test_submit_embeddings_strips_empty_and_unknown_langs(client, temp_db):
    """Empty strings and non-en/es keys are dropped; a present non-empty one wins."""
    guid = str(uuid.uuid4())
    resp = client.post(
        "/submit_embeddings",
        json={"sermon_guid": guid, "texts": {"en": "  ", "es": "Hola.", "fr": "Bonjour.", "de": ""}},
    )
    assert resp.status_code == 201
    conn = _db(temp_db)
    row = conn.execute("SELECT payload_json FROM embeddings WHERE sermon_guid = ?", (guid,)).fetchone()
    conn.close()
    assert json.loads(row["payload_json"]) == {"es": "Hola."}


def test_submit_embeddings_invalid_guid(client):
    resp = client.post(
        "/submit_embeddings",
        json={"sermon_guid": "not-a-uuid", "texts": {"en": "Hello."}},
    )
    assert resp.status_code == 400
    assert "sermon_guid" in resp.get_json()["error"]


def test_submit_embeddings_missing_guid(client):
    resp = client.post("/submit_embeddings", json={"texts": {"en": "Hello."}})
    assert resp.status_code == 400


def test_submit_embeddings_texts_not_dict(client):
    guid = str(uuid.uuid4())
    resp = client.post("/submit_embeddings", json={"sermon_guid": guid, "texts": "Hello."})
    assert resp.status_code == 400
    assert "texts" in resp.get_json()["error"]


def test_submit_embeddings_all_empty_texts(client):
    guid = str(uuid.uuid4())
    resp = client.post(
        "/submit_embeddings",
        json={"sermon_guid": guid, "texts": {"en": "   ", "es": ""}},
    )
    assert resp.status_code == 400


def test_submit_embeddings_idempotent_resubmit(client, temp_db):
    """Re-submitting the same GUID resets the row to pending with fresh texts and
    a cleared result (mirrors /submit_chapters UPSERT)."""
    guid = str(uuid.uuid4())
    client.post("/submit_embeddings", json={"sermon_guid": guid, "texts": {"en": "First."}})

    # Simulate the worker having completed the first run.
    conn = _db(temp_db)
    conn.execute(
        "UPDATE embeddings SET status='completed', result_json=?, updated_at=? WHERE sermon_guid=?",
        (json.dumps({"en": [{"idx": 0, "text": "First.", "embedding": [0.1]}]}), "2026-01-01 00:00:00", guid),
    )
    conn.commit()
    conn.close()

    # Re-submit with different text.
    resp = client.post("/submit_embeddings", json={"sermon_guid": guid, "texts": {"en": "Second."}})
    assert resp.status_code == 201

    conn = _db(temp_db)
    rows = conn.execute("SELECT * FROM embeddings WHERE sermon_guid = ?", (guid,)).fetchall()
    conn.close()
    assert len(rows) == 1  # UPSERT, not a duplicate insert
    assert rows[0]["status"] == "pending"
    assert json.loads(rows[0]["payload_json"]) == {"en": "Second."}
    assert rows[0]["result_json"] is None
    assert rows[0]["updated_at"] is None


# ---------------------------------------------------------------------------
# /embeddings_status route
# ---------------------------------------------------------------------------

def test_embeddings_status_not_found(client):
    resp = client.get(f"/embeddings_status/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_embeddings_status_pending_shape(client, temp_db):
    guid = str(uuid.uuid4())
    client.post("/submit_embeddings", json={"sermon_guid": guid, "texts": {"en": "Hello."}})
    resp = client.get(f"/embeddings_status/{guid}")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["sermon_guid"] == guid
    assert body["status"] == "pending"
    assert body["embeddings"] == {}  # empty until completed


def test_embeddings_status_completed_shape(client, temp_db):
    guid = str(uuid.uuid4())
    client.post("/submit_embeddings", json={"sermon_guid": guid, "texts": {"en": "Hello."}})
    result = {
        "en": [{"idx": 0, "text": "Hello.", "embedding": [0.1, 0.2]}],
        "es": [{"idx": 0, "text": "Hola.", "embedding": [0.3, 0.4]}],
    }
    conn = _db(temp_db)
    conn.execute(
        "UPDATE embeddings SET status='completed', result_json=? WHERE sermon_guid=?",
        (json.dumps(result), guid),
    )
    conn.commit()
    conn.close()

    resp = client.get(f"/embeddings_status/{guid}")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "completed"
    assert body["embeddings"] == result
    assert "en" in body["embeddings"] and "es" in body["embeddings"]


# ---------------------------------------------------------------------------
# Worker: _process_embedding_cycle (the loop body) with embed_chunks mocked.
# ---------------------------------------------------------------------------

def _seed_pending(temp_db, guid, texts):
    conn = _db(temp_db)
    conn.execute(
        "INSERT INTO embeddings (sermon_guid, payload_json, status) VALUES (?, ?, 'pending')",
        (guid, json.dumps(texts)),
    )
    conn.commit()
    conn.close()


def test_worker_cycle_completes_job(temp_db, monkeypatch):
    """A pending job with en+es text completes; result_json carries both languages."""
    guid = str(uuid.uuid4())
    _seed_pending(temp_db, guid, {"en": "English transcript.", "es": "Transcripcion en espanol."})

    calls = []

    def fake_embed_chunks(text):
        calls.append(text)
        return [{"idx": 0, "text": text, "embedding": [0.0] * 1024}]

    monkeypatch.setattr(worker_module, "embed_chunks", fake_embed_chunks)

    conn = _db(temp_db)
    worker_module._process_embedding_cycle(conn)
    conn.close()

    conn = _db(temp_db)
    row = conn.execute("SELECT * FROM embeddings WHERE sermon_guid = ?", (guid,)).fetchone()
    conn.close()
    assert row["status"] == "completed"
    assert row["updated_at"] is not None
    result = json.loads(row["result_json"])
    assert set(result.keys()) == {"en", "es"}
    assert result["en"][0]["embedding"] == [0.0] * 1024
    assert len(calls) == 2  # called once per language


def test_worker_cycle_only_english(temp_db, monkeypatch):
    """A job with only English text produces an en-only result and never calls es."""
    guid = str(uuid.uuid4())
    _seed_pending(temp_db, guid, {"en": "English only transcript."})

    monkeypatch.setattr(
        worker_module, "embed_chunks",
        lambda text: [{"idx": 0, "text": text, "embedding": [1.0] * 1024}],
    )

    conn = _db(temp_db)
    worker_module._process_embedding_cycle(conn)
    conn.close()

    conn = _db(temp_db)
    row = conn.execute("SELECT result_json, status FROM embeddings WHERE sermon_guid = ?", (guid,)).fetchone()
    conn.close()
    assert row["status"] == "completed"
    result = json.loads(row["result_json"])
    assert set(result.keys()) == {"en"}


def test_worker_cycle_marks_error_on_embed_failure(temp_db, monkeypatch):
    """If embed_chunks raises (a failed/short vector upstream), the job goes to
    'error' (so it re-runs) and result_json stays NULL — never a partial store."""
    guid = str(uuid.uuid4())
    _seed_pending(temp_db, guid, {"en": "English transcript.", "es": "Espanol."})

    def boom(text):
        raise RuntimeError("Embedding has 512 dims, expected 1024")

    monkeypatch.setattr(worker_module, "embed_chunks", boom)

    conn = _db(temp_db)
    worker_module._process_embedding_cycle(conn)
    conn.close()

    conn = _db(temp_db)
    row = conn.execute("SELECT status, result_json, updated_at FROM embeddings WHERE sermon_guid = ?", (guid,)).fetchone()
    conn.close()
    assert row["status"] == "error"
    assert row["result_json"] is None
    assert row["updated_at"] is not None  # set so the 24h cleanup can purge it


def test_worker_cycle_purges_old_completed(temp_db, monkeypatch):
    """The cleanup step deletes completed/error rows older than 24h."""
    guid_old = str(uuid.uuid4())
    conn = _db(temp_db)
    conn.execute(
        "INSERT INTO embeddings (sermon_guid, payload_json, status, updated_at) "
        "VALUES (?, ?, 'completed', '2000-01-01 00:00:00')",
        (guid_old, json.dumps({"en": "old"})),
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(worker_module, "embed_chunks", lambda text: [])

    conn = _db(temp_db)
    worker_module._process_embedding_cycle(conn)
    conn.close()

    conn = _db(temp_db)
    row = conn.execute("SELECT 1 FROM embeddings WHERE sermon_guid = ?", (guid_old,)).fetchone()
    conn.close()
    assert row is None  # purged


# ---------------------------------------------------------------------------
# embed_chunks: chunking + the _embed_text contract (Ollama mocked).
# ---------------------------------------------------------------------------

def test_embed_chunks_skips_short_and_assigns_idx(monkeypatch):
    """Chunks under EMBED_MIN_CHARS are skipped; idx is the ORIGINAL paragraph
    index (gaps allowed), matching embed_sermons.py."""
    import aiWork

    # Two real paragraphs plus a tiny one in the middle (which must be skipped).
    paras = ["A" * 30, "x", "B" * 30]
    monkeypatch.setattr(aiWork, "split_transcript_to_paragraphs", lambda text: paras)
    monkeypatch.setattr(aiWork, "_embed_text", lambda text: [0.5] * 1024)

    chunks = aiWork.embed_chunks("ignored")
    assert [c["idx"] for c in chunks] == [0, 2]  # idx 1 (the short one) skipped
    assert all(len(c["embedding"]) == 1024 for c in chunks)
    assert chunks[0]["text"] == "A" * 30


def test_embed_chunks_raises_on_no_usable_chunks(monkeypatch):
    import aiWork

    monkeypatch.setattr(aiWork, "split_transcript_to_paragraphs", lambda text: ["short", "x"])
    monkeypatch.setattr(aiWork, "_embed_text", lambda text: [0.5] * 1024)
    with pytest.raises(ValueError):
        aiWork.embed_chunks("ignored")


def test_embed_text_posts_correct_payload(monkeypatch):
    """_embed_text POSTs {model, prompt} to {OLLAMA_BASE_URL}/api/embeddings and
    reads the 'embedding' list — the exact contract the web app uses."""
    import aiWork

    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama.test:11434")
    monkeypatch.delenv("EMBED_MODEL", raising=False)

    captured = {}

    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"embedding": [0.1] * 1024}

    def fake_post(url, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResp()

    monkeypatch.setattr(aiWork.requests, "post", fake_post)

    emb = aiWork._embed_text("trust God")
    assert captured["url"] == "http://ollama.test:11434/api/embeddings"
    assert captured["json"] == {"model": "bge-m3", "prompt": "trust God"}
    assert len(emb) == 1024


def test_embed_text_raises_on_wrong_dim(monkeypatch):
    """A non-1024 vector must raise (the web app would reject it), not be returned."""
    import aiWork

    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama.test:11434")

    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"embedding": [0.1] * 512}

    monkeypatch.setattr(aiWork.requests, "post", lambda *a, **k: FakeResp())
    with pytest.raises(RuntimeError, match="512 dims"):
        aiWork._embed_text("trust God")


def test_embed_text_raises_without_base_url(monkeypatch):
    import aiWork

    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="OLLAMA_BASE_URL"):
        aiWork._embed_text("trust God")
