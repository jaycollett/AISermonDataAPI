from flask import Flask, request, jsonify, g
import sqlite3
import os
import time
import logging
import threading
from worker import process_sermon_jobs

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


if __name__ == "__main__":
    logging.info("🔥 Initializing the database...")
    init_db()  # 💡 Ensure this runs before anything else

    logging.info("🔥 Starting Sermon API Server...")
    
    logging.info("🔥 Starting sermon worker thread...")
    time.sleep(5)
    worker_thread = threading.Thread(target=process_sermon_jobs, daemon=True)
    worker_thread.start()

    logging.info("✅ Sermon API Server started successfully.")
    app.run(host="0.0.0.0", port=5090, debug=True, use_reloader=False)
