import sqlite3
import time
import logging
import codecs
from datetime import datetime
from aiWork import generate_sermon_analysis

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
    """Processes pending sermons and extracts insights."""
    while True:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

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
                    summary_en, summary_es, topics_en, topics_es, bible_refs_en, bible_refs_es, sermon_style_en, sermon_style_es, sentiment_en, sentiment_es, key_quotes_en, key_quotes_es = generate_sermon_analysis(transcription)

                    # Ensure proper UTF-8 handling before saving to the database
                    summary_es = decode_unicode(summary_es)
                    topics_es = decode_unicode(topics_es)
                    bible_refs_es = decode_unicode(bible_refs_es)
                    sermon_style_es = decode_unicode(sermon_style_es)
                    sentiment_es = decode_unicode(sentiment_es)
                    key_quotes_es = decode_unicode(key_quotes_es)



                    finished_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

                    # Update database
                    cursor.execute(
                        """UPDATE sermons 
                           SET ai_summary = ?, ai_summary_es = ?, bible_books = ?, bible_books_es = ?, 
                               topics = ?, topics_es = ?, sermon_style = ?, sermon_style_es = ?, 
                               sentiment = ?, sentiment_es = ?, key_quotes = ?, key_quotes_es = ?, 
                               status = 'completed', updated_at = ?
                           WHERE id = ?""",
                        (summary_en, summary_es, bible_refs_en, bible_refs_es, topics_en, topics_es, sermon_style_en, sermon_style_es, sentiment_en, sentiment_es, key_quotes_en, key_quotes_es, finished_at, sermon_id)
                    )
                    conn.commit()

                    logging.info(f"✅ Sermon {sermon_guid} processed successfully.")

                except Exception as e:
                    logging.error(f"❌ Error processing sermon {sermon_guid}: {e}")
                    cursor.execute("UPDATE sermons SET status = 'error' WHERE id = ?", (sermon_id,))
                    conn.commit()

            conn.close()
            time.sleep(PROCESS_INTERVAL)
        except Exception as e:
            logging.error(f"🚨 Worker error: {e}")
            time.sleep(PROCESS_INTERVAL)


if __name__ == "__main__":
    logging.info("🔥 Starting sermon processing worker...")
    process_sermon_jobs()
