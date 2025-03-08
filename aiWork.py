import openai
import re
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Load OpenAI API key from environment variable
openai.api_key = os.getenv("OPENAI_API_KEY")

if not openai.api_key:
    logging.error("OpenAI API key not found. Please set OPENAI_API_KEY environment variable.")
    exit(1)

import openai
import re
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Load OpenAI API key from environment variable
openai.api_key = os.getenv("OPENAI_API_KEY")

if not openai.api_key:
    logging.error("OpenAI API key not found. Please set OPENAI_API_KEY environment variable.")
    exit(1)

def generate_sermon_analysis(text):
    """Generates a sermon summary, topics, Bible references, sentiment, and key quotes in both English and Mexican Spanish."""
    
    prompt = f"""
    Analyze the following Christian sermon transcription and extract insights in **both English and Mexican Spanish**:

    1. **Summary**: Provide a concise, factual summary of the pastor's sermon in **5-6 sentences**.
    2. **Topics**: Identify **2-5 major topics** this sermon addresses.
    3. **Bible Books & Verses**: List **all Bible books and specific verse references** mentioned.
    4. **Sermon Style**: Determine if the sermon is **Expository, Topical, Narrative, or Doctrinal**.
    5. **Sentiment**: Identify the **overall tone** (Encouraging, Uplifting, Warning, Teaching, Reflective).
    6. **Key Quotes**: Provide **2-4 of the most impactful or significant quotes** from the sermon.

    **Return all outputs in both English and Mexican Spanish.**
    
    Sermon:
    {text}

    Return strictly formatted as:

    Summary (English):
    [English summary]

    Summary (Mexican Spanish):
    [Spanish summary]

    Topics (English):
    [comma-separated list]

    Topics (Mexican Spanish):
    [comma-separated list]

    Bible Books & Verses (English):
    [comma-separated list]

    Bible Books & Verses (Mexican Spanish):
    [comma-separated list]

    Sermon Style (English):
    [style]

    Sermon Style (Mexican Spanish):
    [style]

    Sentiment (English):
    [sentiment]

    Sentiment (Mexican Spanish):
    [sentiment]

    Key Quotes (English):
    [quote1] | [quote2]

    Key Quotes (Mexican Spanish):
    [quote1] | [quote2]
    """

    client = openai.Client()  # Use the new OpenAI Client class

    response = client.chat.completions.create(  # Updated method syntax
        model="gpt-4-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
    )

    content = response.choices[0].message.content

    summary_en = re.search(r"Summary \(English\):\s*(.*?)\n\nSummary \(Mexican Spanish\):", content, re.DOTALL).group(1).strip()
    summary_es = re.search(r"Summary \(Mexican Spanish\):\s*(.*?)\n\nTopics \(English\):", content, re.DOTALL).group(1).strip()
    topics_en = re.search(r"Topics \(English\):\s*(.*?)\n\nTopics \(Mexican Spanish\):", content).group(1).strip()
    topics_es = re.search(r"Topics \(Mexican Spanish\):\s*(.*?)\n\nBible Books & Verses \(English\):", content).group(1).strip()
    bible_refs_en = re.search(r"Bible Books & Verses \(English\):\s*(.*?)\n\nBible Books & Verses \(Mexican Spanish\):", content).group(1).strip()
    bible_refs_es = re.search(r"Bible Books & Verses \(Mexican Spanish\):\s*(.*?)\n\nSermon Style \(English\):", content).group(1).strip()
    sermon_style_en = re.search(r"Sermon Style \(English\):\s*(.*?)\n\nSermon Style \(Mexican Spanish\):", content).group(1).strip()
    sermon_style_es = re.search(r"Sermon Style \(Mexican Spanish\):\s*(.*?)\n\nSentiment \(English\):", content).group(1).strip()
    sentiment_en = re.search(r"Sentiment \(English\):\s*(.*?)\n\nSentiment \(Mexican Spanish\):", content).group(1).strip()
    sentiment_es = re.search(r"Sentiment \(Mexican Spanish\):\s*(.*?)\n\nKey Quotes \(English\):", content).group(1).strip()
    key_quotes_en = re.search(r"Key Quotes \(English\):\s*(.*?)\n\nKey Quotes \(Mexican Spanish\):", content).group(1).strip()
    key_quotes_es = re.search(r"Key Quotes \(Mexican Spanish\):\s*(.*)", content).group(1).strip()

    return summary_en, summary_es, topics_en, topics_es, bible_refs_en, bible_refs_es, sermon_style_en, sermon_style_es, sentiment_en, sentiment_es, key_quotes_en, key_quotes_es
