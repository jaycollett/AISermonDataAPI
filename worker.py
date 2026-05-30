import sqlite3
import json
import time
import logging
import codecs
from datetime import datetime
from aiWork import generate_sermon_analysis, generate_chapters
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")

DATABASE = "jobs.db"
PROCESS_INTERVAL = 30  # Seconds between processing cycles

def get_db_connection():
    """Creates a new database connection."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def decode_unicode(text):
    """Ensures proper Unicode handling without forcing unnecessary decoding."""
    if isinstance(text, str):  # Ensure it's a string
        return text.encode("utf-8").decode("utf-8")  # ✅ Prevents over-decoding issues
    return text  # Return unchanged if None or not a string

def process_sermon_jobs():
    """Processes pending sermons, extracts insights, and cleans up old finished jobs."""
    while True:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Cleanup old jobs:
            # Delete jobs with status 'completed' or 'error'
            # that have an updated_at timestamp 24 or more hours ago.
            cutoff_time = (datetime.utcnow() - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute(
                """
                DELETE FROM sermons 
                WHERE (status = 'completed' OR status = 'error') 
                  AND updated_at IS NOT NULL 
                  AND updated_at <= ?
                """,
                (cutoff_time,)
            )
            conn.commit()

            # Process pending sermons
            cursor.execute("SELECT * FROM sermons WHERE status = 'pending' LIMIT 5")
            sermons = cursor.fetchall()

            if not sermons:
                logging.info("⏳ No pending sermons. Waiting...")

            for sermon in sermons:
                sermon_id = sermon["id"]
                sermon_guid = sermon["sermon_guid"]
                transcription = sermon["transcription"]

                try:
                    # Extract AI-generated insights
                    summary_en, summary_es, topics_en, topics_es, bible_refs_en, bible_refs_es, \
                    sermon_style_en, sermon_style_es, sentiment_en, sentiment_es, key_quotes_en, key_quotes_es = generate_sermon_analysis(transcription)

                    # Ensure proper UTF-8 handling before saving to the database
                    summary_es = decode_unicode(summary_es)
                    topics_es = decode_unicode(topics_es)
                    bible_refs_es = decode_unicode(bible_refs_es)
                    sermon_style_es = decode_unicode(sermon_style_es)
                    sentiment_es = decode_unicode(sentiment_es)
                    key_quotes_es = decode_unicode(key_quotes_es)

                    finished_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

                    # Update database with completed job
                    cursor.execute(
                        """UPDATE sermons 
                           SET ai_summary = ?, ai_summary_es = ?, bible_books = ?, bible_books_es = ?, 
                               topics = ?, topics_es = ?, sermon_style = ?, sermon_style_es = ?, 
                               sentiment = ?, sentiment_es = ?, key_quotes = ?, key_quotes_es = ?, 
                               status = 'completed', updated_at = ?
                           WHERE id = ?""",
                        (summary_en, summary_es, bible_refs_en, bible_refs_es,
                         topics_en, topics_es, sermon_style_en, sermon_style_es,
                         sentiment_en, sentiment_es, key_quotes_en, key_quotes_es, finished_at, sermon_id)
                    )
                    conn.commit()

                    logging.info(f"✅ Sermon {sermon_guid} processed successfully.")

                except Exception as e:
                    logging.error(f"❌ Error processing sermon {sermon_guid}: {e}")
                    # Set updated_at on error rows so the 24h cleanup query can
                    # eventually purge them. Without this, errored rows linger
                    # forever and orchestrators polling for them block forever.
                    error_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                    cursor.execute(
                        "UPDATE sermons SET status = 'error', updated_at = ? WHERE id = ?",
                        (error_at, sermon_id),
                    )
                    conn.commit()

            conn.close()
            time.sleep(PROCESS_INTERVAL)
        except Exception as e:
            logging.error(f"🚨 Worker error: {e}")
            time.sleep(PROCESS_INTERVAL)
            
def _normalize_chapters(raw):
    """Validate + normalize the condenser's output before it is stored.

    Accepts the list returned by generate_chapters() and returns a clean list
    of {idx, start_seconds, label_en, label_es} sorted by start_seconds with idx
    renumbered 0..n. Raises ValueError on anything unusable so the worker's
    try/except flips the row to status='error' (and the job re-runs later).
    """
    if not isinstance(raw, list) or not raw:
        raise ValueError("generate_chapters returned no chapters")

    cleaned = []
    for seg in raw:
        if not isinstance(seg, dict):
            raise ValueError("chapter entry is not an object")
        start = int(seg["start_seconds"])
        label_en = str(seg.get("label_en") or "").strip()
        label_es = str(seg.get("label_es") or "").strip()
        if start < 0 or not label_en or not label_es:
            raise ValueError("chapter missing start_seconds or a label")
        cleaned.append({
            "start_seconds": start,
            "label_en": label_en[:120],
            "label_es": label_es[:120],
        })

    cleaned.sort(key=lambda c: c["start_seconds"])
    for i, c in enumerate(cleaned):
        c["idx"] = i
    return cleaned


def process_chapter_jobs():
    """Processes pending chapter-condensing jobs: reads the stored timings, runs
    the LLM condenser, and stores the resulting markers. Fully independent of
    the sermon AI-content worker (its own table + loop)."""
    while True:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Cleanup: purge completed/error chapter jobs older than 24h.
            cutoff_time = (datetime.utcnow() - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute(
                """
                DELETE FROM chapters
                WHERE (status = 'completed' OR status = 'error')
                  AND updated_at IS NOT NULL
                  AND updated_at <= ?
                """,
                (cutoff_time,),
            )
            conn.commit()

            cursor.execute("SELECT * FROM chapters WHERE status = 'pending' LIMIT 5")
            jobs = cursor.fetchall()

            if not jobs:
                logging.info("⏳ No pending chapter jobs. Waiting...")

            for job in jobs:
                chapter_id = job["id"]
                sermon_guid = job["sermon_guid"]

                try:
                    timings = json.loads(job["timings_json"])
                    chapters = _normalize_chapters(generate_chapters(timings))

                    finished_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                    cursor.execute(
                        """UPDATE chapters
                           SET chapters_json = ?, status = 'completed', updated_at = ?
                           WHERE id = ?""",
                        (json.dumps(chapters), finished_at, chapter_id),
                    )
                    conn.commit()
                    logging.info(f"✅ Chapters for {sermon_guid} generated ({len(chapters)} markers).")

                except Exception as e:
                    logging.error(f"❌ Error generating chapters for {sermon_guid}: {e}")
                    error_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                    cursor.execute(
                        "UPDATE chapters SET status = 'error', updated_at = ? WHERE id = ?",
                        (error_at, chapter_id),
                    )
                    conn.commit()

            conn.close()
            time.sleep(PROCESS_INTERVAL)
        except Exception as e:
            logging.error(f"🚨 Chapter worker error: {e}")
            time.sleep(PROCESS_INTERVAL)


if __name__ == "__main__":
    logging.info("🔥 Starting sermon processing worker...")
    process_sermon_jobs()
