from flask import Flask, request, jsonify, g
import sqlite3
import json
import uuid
import os
import time
import logging
import threading
from worker import process_sermon_jobs, process_chapter_jobs, process_embedding_jobs

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)
DATABASE = 'jobs.db'

def get_db():
    """Connects to the database."""
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

def init_db():
    """Initializes the database with necessary tables."""
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sermons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sermon_guid TEXT NOT NULL UNIQUE,
                transcription TEXT NOT NULL,
                ai_summary TEXT DEFAULT NULL,
                ai_summary_es TEXT DEFAULT NULL,
                bible_books TEXT DEFAULT NULL,
                bible_books_es TEXT DEFAULT NULL,
                topics TEXT DEFAULT NULL,
                topics_es TEXT DEFAULT NULL,
                sermon_style TEXT DEFAULT NULL,
                sermon_style_es TEXT DEFAULT NULL,
                sentiment TEXT DEFAULT NULL,
                sentiment_es TEXT DEFAULT NULL,
                key_quotes TEXT DEFAULT NULL,
                key_quotes_es TEXT DEFAULT NULL,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chapters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sermon_guid TEXT NOT NULL UNIQUE,
                timings_json TEXT NOT NULL,
                chapters_json TEXT DEFAULT NULL,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS embeddings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sermon_guid TEXT NOT NULL UNIQUE,
                payload_json TEXT NOT NULL,
                result_json TEXT DEFAULT NULL,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT NULL
            )
        ''')
        db.commit()
    logging.info("✅ Database initialized successfully.")

@app.teardown_appcontext
def close_connection(exception):
    """Closes database connection at the end of request."""
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

@app.route('/submit_sermon', methods=['POST'])
def submit_sermon():
    """Endpoint to submit a sermon transcription for AI processing."""
    try:
        data = request.get_json()
        sermon_guid = data.get('sermon_guid')
        transcription = data.get('transcription')

        if not all([sermon_guid, transcription]):
            return jsonify({"error": "Missing required fields"}), 400

        db = get_db()
        cursor = db.cursor()

        # Check if sermon already exists
        cursor.execute("SELECT id FROM sermons WHERE sermon_guid = ?", (sermon_guid,))
        if cursor.fetchone():
            return jsonify({"error": "Sermon already exists"}), 409

        cursor.execute('''
            INSERT INTO sermons (sermon_guid, transcription, status)
            VALUES (?, ?, 'pending')
        ''', (sermon_guid, transcription))
        db.commit()

        return jsonify({"message": "Sermon submitted successfully"}), 201

    except Exception as e:
        logging.exception("Error processing sermon submission.")
        return jsonify({"error": str(e)}), 500

@app.route('/status/<sermon_guid>', methods=['GET'])
def get_sermon_status(sermon_guid):
    """Fetches the processing status of a sermon without returning the transcription."""
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("""
            SELECT sermon_guid, ai_summary, ai_summary_es, bible_books, bible_books_es, 
                   topics, topics_es, sermon_style, sermon_style_es, sentiment, sentiment_es, 
                   key_quotes, key_quotes_es, status, created_at, updated_at
            FROM sermons WHERE sermon_guid = ?
        """, (sermon_guid,))
        
        row = cursor.fetchone()

        if row is None:
            return jsonify({"error": "Sermon not found."}), 404

        return jsonify(dict(row)), 200

    except Exception as e:
        logging.exception("Error retrieving sermon status.")
        return jsonify({"error": str(e)}), 500


def _is_uuid(value):
    """True if value parses as a UUID."""
    try:
        uuid.UUID(str(value))
        return True
    except (ValueError, TypeError, AttributeError):
        return False


@app.route('/submit_chapters', methods=['POST'])
def submit_chapters():
    """Submit a sermon's transcription timings for chapter-marker condensing.

    Independent of the /submit_sermon AI-content job. Re-submission is
    idempotent: an existing row is reset to 'pending' with fresh timings and a
    cleared result, so backfill and re-runs work without a 409.

    Payload: {sermon_guid, timings: [{start: float, end: float, text: str}, ...]}
    """
    try:
        data = request.get_json(silent=True) or {}
        sermon_guid = data.get('sermon_guid')
        timings = data.get('timings')

        if not _is_uuid(sermon_guid):
            return jsonify({"error": "Missing or invalid sermon_guid"}), 400
        if not isinstance(timings, list) or not timings:
            return jsonify({"error": "timings must be a non-empty list"}), 400
        for i, seg in enumerate(timings):
            if (not isinstance(seg, dict)
                    or not isinstance(seg.get('start'), (int, float))
                    or not isinstance(seg.get('end'), (int, float))
                    or not str(seg.get('text') or '').strip()):
                return jsonify(
                    {"error": f"segment {i} needs numeric start/end and non-empty text"}
                ), 400

        timings_json = json.dumps(timings)

        db = get_db()
        cursor = db.cursor()
        # UPSERT keyed on sermon_guid: insert new, or reset an existing row back
        # to 'pending' with the fresh timings (idempotent for backfill/re-runs).
        cursor.execute("SELECT id FROM chapters WHERE sermon_guid = ?", (sermon_guid,))
        if cursor.fetchone():
            cursor.execute(
                """UPDATE chapters
                   SET timings_json = ?, chapters_json = NULL,
                       status = 'pending', updated_at = NULL
                   WHERE sermon_guid = ?""",
                (timings_json, sermon_guid),
            )
        else:
            cursor.execute(
                "INSERT INTO chapters (sermon_guid, timings_json, status) "
                "VALUES (?, ?, 'pending')",
                (sermon_guid, timings_json),
            )
        db.commit()

        return jsonify({"message": "Chapters job submitted"}), 201

    except Exception as e:
        logging.exception("Error processing chapters submission.")
        return jsonify({"error": str(e)}), 500


@app.route('/chapters_status/<sermon_guid>', methods=['GET'])
def get_chapters_status(sermon_guid):
    """Status + result for a chapters job. chapters is [] until completed."""
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "SELECT sermon_guid, status, chapters_json, created_at, updated_at "
            "FROM chapters WHERE sermon_guid = ?",
            (sermon_guid,),
        )
        row = cursor.fetchone()
        if row is None:
            return jsonify({"error": "Chapters job not found."}), 404

        result = dict(row)
        result["chapters"] = json.loads(result.pop("chapters_json") or "[]")
        return jsonify(result), 200

    except Exception as e:
        logging.exception("Error retrieving chapters status.")
        return jsonify({"error": str(e)}), 500


@app.route('/submit_embeddings', methods=['POST'])
def submit_embeddings():
    """Submit a sermon's transcription text(s) for bge-m3 chunk embedding.

    Independent of the /submit_sermon and /submit_chapters jobs. Re-submission
    is idempotent: an existing row is reset to 'pending' with the fresh texts
    and a cleared result, mirroring /submit_chapters, so backfill and re-runs
    work without a 409.

    Payload: {sermon_guid, texts: {en: "<english_transcription>",
                                    es: "<spanish_transcription>"}}
    At least one of en/es must be a non-empty string. The worker chunks each
    provided language and embeds every chunk.
    """
    try:
        data = request.get_json(silent=True) or {}
        sermon_guid = data.get('sermon_guid')
        texts = data.get('texts')

        if not _is_uuid(sermon_guid):
            return jsonify({"error": "Missing or invalid sermon_guid"}), 400
        if not isinstance(texts, dict):
            return jsonify({"error": "texts must be an object"}), 400
        # Keep only en/es keys that carry a non-empty string.
        cleaned_texts = {
            lang: value
            for lang, value in texts.items()
            if lang in ("en", "es") and isinstance(value, str) and value.strip()
        }
        if not cleaned_texts:
            return jsonify(
                {"error": "texts must include at least one non-empty en/es string"}
            ), 400

        payload_json = json.dumps(cleaned_texts)

        db = get_db()
        cursor = db.cursor()
        # UPSERT keyed on sermon_guid: insert new, or reset an existing row back
        # to 'pending' with fresh texts (idempotent for backfill/re-runs).
        cursor.execute("SELECT id FROM embeddings WHERE sermon_guid = ?", (sermon_guid,))
        if cursor.fetchone():
            cursor.execute(
                """UPDATE embeddings
                   SET payload_json = ?, result_json = NULL,
                       status = 'pending', updated_at = NULL
                   WHERE sermon_guid = ?""",
                (payload_json, sermon_guid),
            )
        else:
            cursor.execute(
                "INSERT INTO embeddings (sermon_guid, payload_json, status) "
                "VALUES (?, ?, 'pending')",
                (sermon_guid, payload_json),
            )
        db.commit()

        return jsonify({"message": "Embeddings job submitted"}), 201

    except Exception as e:
        logging.exception("Error processing embeddings submission.")
        return jsonify({"error": str(e)}), 500


@app.route('/embeddings_status/<sermon_guid>', methods=['GET'])
def get_embeddings_status(sermon_guid):
    """Status + result for an embeddings job.

    Returns {sermon_guid, status, embeddings: {en: [...], es: [...]}}. The
    embeddings object is empty ({}) until the job completes. Each language maps
    to a list of {idx, text, embedding:[float x1024]}.
    """
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "SELECT sermon_guid, status, result_json, created_at, updated_at "
            "FROM embeddings WHERE sermon_guid = ?",
            (sermon_guid,),
        )
        row = cursor.fetchone()
        if row is None:
            return jsonify({"error": "Embeddings job not found."}), 404

        result = dict(row)
        result["embeddings"] = json.loads(result.pop("result_json") or "{}")
        return jsonify(result), 200

    except Exception as e:
        logging.exception("Error retrieving embeddings status.")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    logging.info("🔥 Initializing the database...")
    init_db()  # 💡 Ensure this runs before anything else

    logging.info("🔥 Starting Sermon API Server...")
    
    logging.info("🔥 Starting sermon worker thread...")
    time.sleep(5)
    worker_thread = threading.Thread(target=process_sermon_jobs, daemon=True)
    worker_thread.start()

    logging.info("🔥 Starting chapters worker thread...")
    chapter_thread = threading.Thread(target=process_chapter_jobs, daemon=True)
    chapter_thread.start()

    logging.info("🔥 Starting embeddings worker thread...")
    embedding_thread = threading.Thread(target=process_embedding_jobs, daemon=True)
    embedding_thread.start()

    logging.info("✅ Sermon API Server started successfully.")
    app.run(host="0.0.0.0", port=5090, debug=True, use_reloader=False)
