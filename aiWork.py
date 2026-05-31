"""Sermon analysis via Claude Code CLI subprocess.

Invokes the Claude Code CLI (`claude -p`) as a subprocess to produce a
structured sermon analysis. Replaces the previous OpenAI direct-API
implementation.

The function signature `generate_sermon_analysis(text)` returns the same
12-tuple as before so the synchronous worker loop does not need to change.
"""

import json
import logging
import os
import re
import shutil
import subprocess
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Max wall time for a single Claude Code CLI invocation. Opus with --effort medium
# on a long transcription typically completes in 20-60s; 300s is a safety ceiling.
CLAUDE_TIMEOUT_SECONDS = 300

# Threshold above which the prompt is piped via stdin instead of -p. Most shells
# tolerate ~128KB argv; we stay well below that.
PROMPT_ARG_MAX_BYTES = 64 * 1024


def _find_claude_binary() -> str:
    """Locate the claude CLI binary.

    Mirrors the AutoInvestor pattern: prefer PATH, fall back to common
    npm-global and user-install locations.
    """
    for candidate in (
        shutil.which("claude"),
        "/usr/local/bin/claude",
        "/home/appuser/.claude/local/claude",
        "/root/.claude/local/claude",
        os.path.expanduser("~/.claude/local/claude"),
    ):
        if candidate and Path(candidate).exists():
            return candidate
    return "claude"


def _build_prompt(text: str) -> str:
    """Build the sermon-analysis prompt.

    The body is intentionally identical to the previous OpenAI prompt so the
    downstream regex parser in this same file still matches.
    """
    return f"""
    Analyze the following Christian sermon transcription and extract insights in **both English and Mexican Spanish**:

    1. **Summary**: Provide a concise, factual summary of the pastor's sermon in **5-6 sentences**.
    2. **Topics**: Identify **2-5 major topics** this sermon addresses.
    3. **Bible Books & Verses**: List **all Bible books and specific verse references** mentioned.
    4. **Sermon Style**: Determine if the sermon is **Expository, Topical, Narrative, or Doctrinal**.
    5. **Sentiment**: Identify the **overall tone** (Encouraging, Uplifting, Warning, Teaching, Reflective).
    6. **Key Quotes**: Provide **3-4 of the most impactful or significant quotes** from the sermon.

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


def _invoke_claude(prompt: str) -> str:
    """Run the Claude Code CLI and return its stdout text.

    Raises on non-zero exit or timeout so the worker's existing try/except
    flips the row to status='error'.
    """
    claude_bin = _find_claude_binary()

    base_cmd = [
        claude_bin,
        "--output-format", "text",
        "--allowedTools", "",
        "--max-turns", "2",
        "--model", "claude-opus-4-7",
        "--effort", "medium",
    ]

    env = os.environ.copy()
    oauth_token = env.get("CLAUDE_CODE_OAUTH_TOKEN")
    if not oauth_token:
        raise RuntimeError(
            "CLAUDE_CODE_OAUTH_TOKEN not set; cannot invoke Claude Code CLI."
        )
    # PVC-backed state dir so OAuth/session state persists across pod restarts.
    env.setdefault("CLAUDE_CONFIG_DIR", "/data/claude-home")
    Path(env["CLAUDE_CONFIG_DIR"]).mkdir(parents=True, exist_ok=True)

    prompt_bytes = prompt.encode("utf-8")

    if len(prompt_bytes) <= PROMPT_ARG_MAX_BYTES:
        cmd = base_cmd + ["-p", prompt]
        stdin_input = None
    else:
        # Long transcript: write the prompt to a temp file and pipe it on stdin.
        # `claude -p` with no positional prompt and stdin attached reads the
        # prompt from stdin.
        cmd = base_cmd + ["-p"]
        stdin_input = prompt

    logging.info(
        "Invoking Claude Code CLI (prompt=%d bytes, mode=%s)",
        len(prompt_bytes),
        "stdin" if stdin_input else "argv",
    )

    try:
        result = subprocess.run(
            cmd,
            input=stdin_input,
            capture_output=True,
            text=True,
            env=env,
            timeout=CLAUDE_TIMEOUT_SECONDS,
            check=False,
        )
    except FileNotFoundError as e:
        raise RuntimeError(
            f"Claude Code CLI binary not found at {claude_bin}: {e}"
        ) from e
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(
            f"Claude Code CLI timed out after {CLAUDE_TIMEOUT_SECONDS}s"
        ) from e

    if result.returncode != 0:
        stderr_excerpt = (result.stderr or "")[:1000]
        raise RuntimeError(
            f"Claude Code CLI exited with code {result.returncode}: {stderr_excerpt}"
        )

    stdout = (result.stdout or "").strip()
    if not stdout:
        raise RuntimeError("Claude Code CLI returned empty stdout.")

    return stdout


def generate_sermon_analysis(text):
    """Generate sermon analysis in English and Mexican Spanish.

    Returns a 12-tuple:
        (summary_en, summary_es, topics_en, topics_es,
         bible_refs_en, bible_refs_es, sermon_style_en, sermon_style_es,
         sentiment_en, sentiment_es, key_quotes_en, key_quotes_es)
    """
    prompt = _build_prompt(text)
    content = _invoke_claude(prompt)

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

    return (
        summary_en, summary_es, topics_en, topics_es,
        bible_refs_en, bible_refs_es, sermon_style_en, sermon_style_es,
        sentiment_en, sentiment_es, key_quotes_en, key_quotes_es,
    )


# Coalesce raw transcription segments into ~this many seconds per block before
# prompting. The chapter granularity we want (5-12 over a ~30 min sermon) is far
# coarser than the raw ~1-5s segments, so blocking keeps the prompt compact
# without losing the resolution needed to place a chapter start.
CHAPTER_BLOCK_SECONDS = 20.0


def _build_chapters_prompt(timings):
    """Coalesce timed segments into ~CHAPTER_BLOCK_SECONDS blocks and build the
    chapter-segmentation prompt. Each block is one line: "[<seconds>] <text>"."""
    blocks = []
    block_start = None
    parts = []
    for seg in timings:
        try:
            start = float(seg.get("start") or 0.0)
        except (TypeError, ValueError):
            start = 0.0
        text = str(seg.get("text") or "").strip()
        if not text:
            continue
        if block_start is None:
            block_start = start
        parts.append(text)
        if start - block_start >= CHAPTER_BLOCK_SECONDS:
            blocks.append((int(block_start), " ".join(parts)))
            block_start = None
            parts = []
    if parts:
        blocks.append((int(block_start or 0.0), " ".join(parts)))

    transcript = "\n".join(f"[{s}] {t}" for s, t in blocks)

    return f"""You are segmenting a Christian sermon into chapter markers for an audio player.

Below is the sermon transcript as timestamped blocks, one per line, formatted "[<seconds>] <text>" where <seconds> is the audio position in whole seconds.

Identify between 5 and 12 natural chapters — major shifts in the sermon such as the opening/welcome, the scripture reading, each main teaching point, a key illustration, the application, and the closing/benediction. For each chapter provide:
- "start": the integer audio position in seconds where the chapter begins (use the [seconds] value of the block where it starts)
- "label_en": a short, descriptive English title in Title Case, 2 to 6 words, no trailing punctuation
- "label_es": the Mexican Spanish translation of label_en

Requirements:
- The first chapter MUST have "start": 0.
- Chapters MUST be ordered by increasing start and must not repeat a start value.
- Prefer specific, content-based titles over generic ones.
- Output between 5 and 12 chapters depending on the sermon's length and structure.

Return ONLY a JSON array and nothing else, in exactly this shape:
[
  {{"start": 0, "label_en": "Welcome and Prayer", "label_es": "Bienvenida y oración"}},
  {{"start": 95, "label_en": "Reading from Matthew 21", "label_es": "Lectura de Mateo 21"}}
]

Transcript:
{transcript}
"""


def _parse_chapters_response(content):
    """Extract the JSON array of chapters from the model's response. Lenient on
    surrounding prose/markdown fences; the worker's _normalize_chapters does the
    final validation (labels present, sort, renumber, cap)."""
    match = re.search(r"\[.*\]", content, re.DOTALL)
    if not match:
        raise RuntimeError("No JSON array found in chapters response")
    data = json.loads(match.group(0))
    if not isinstance(data, list):
        raise RuntimeError("Chapters response is not a JSON array")

    chapters = []
    for ch in data:
        if not isinstance(ch, dict):
            continue
        try:
            start = int(round(float(ch.get("start"))))
        except (TypeError, ValueError):
            continue  # unusable start — drop this entry
        chapters.append({
            "start_seconds": max(0, start),
            "label_en": str(ch.get("label_en") or "").strip(),
            "label_es": str(ch.get("label_es") or "").strip(),
        })
    return chapters


def generate_chapters(timings):
    """Condense transcription timings into chapter markers via the Claude CLI.

    Input — `timings`: a time-ordered list of segment dicts (English only), each
    {"start": float_seconds, "end": float_seconds, "text": str}.

    Return — a list of chapter dicts {"start_seconds": int, "label_en": str,
    "label_es": str}, earliest first, with the first chapter forced to start at 0.
    The worker (worker._normalize_chapters) renumbers idx, caps labels, re-sorts,
    and rejects the job (status='error') if the result is empty or any chapter is
    missing a label — so partial/garbage output is safe and simply re-runs.
    """
    if not isinstance(timings, list) or not timings:
        raise RuntimeError("generate_chapters received empty timings")

    prompt = _build_chapters_prompt(timings)
    content = _invoke_claude(prompt)
    chapters = _parse_chapters_response(content)

    chapters.sort(key=lambda c: c["start_seconds"])
    if chapters:
        # Guarantee coverage from the very start of the audio.
        chapters[0]["start_seconds"] = 0
    return chapters


# ---------------------------------------------------------------------------
# Embeddings (bge-m3 via Ollama)
#
# This block produces the semantic-search chunk embeddings the web app stores
# at /api/sermon_embeddings. The web app validates each chunk's vector length
# EXACTLY (== EMBED_DIM, default 1024) and rejects the whole POST otherwise, so
# everything here raises on the first bad/empty embedding rather than emitting a
# short vector — the worker then flips the job to status='error' and it re-runs.
#
# CRITICAL — chunk-boundary parity: the chunking below is a verbatim copy of the
# web app's sermon_search/utils/text.py::split_transcript_to_paragraphs (and its
# helper _bucket_plain_paragraphs + PARAGRAPH_TARGET_LENGTH). The boundaries MUST
# match the corpus backfill (build_utils/embed_sermons.py) so re-embeds line up.
# If you change the splitter in the web app, change it here too. The embed call
# is the requests-based equivalent of text web app's services/embeddings.py::embed_text.
# ---------------------------------------------------------------------------

import html as _html

import bleach
import requests

# Sentence-bucketing target — copied from the web app's text.py so chunk
# boundaries are identical to the corpus backfill.
PARAGRAPH_TARGET_LENGTH = 665

# Mirror embed_sermons.py: chunks shorter than this are skipped (too small to
# carry useful signal, and the web app would reject an empty-ish vector anyway).
EMBED_MIN_CHARS = 20

# Expected bge-m3 dimensionality. The web app rejects any chunk whose vector is
# not exactly this length, so we assert it here before returning.
EMBED_DIM = 1024

# Per-chunk Ollama timeout. Matches embed_sermons.py (which uses 30s for the
# backfill, vs the web app's 8s query-time default).
EMBED_TIMEOUT_SECONDS = 30.0

_entity_unescape = _html.unescape


def _bucket_plain_paragraphs(text, min_length=PARAGRAPH_TARGET_LENGTH):
    """Sentence-bucket plain text into paragraphs of roughly ``min_length``.

    Verbatim copy of the web app's text.py helper of the same name. Keep in
    sync with sermon_search/utils/text.py so embedding chunk boundaries match
    the corpus backfill.
    """
    if not text:
        return []
    if "\n\n" in text:
        return [p.strip() for p in text.split("\n\n") if p.strip()]
    sentences = re.split(r'(?<=[.!?])\s+', text)
    paragraphs = []
    current_para = ""
    for sentence in sentences:
        candidate = current_para + " " + sentence if current_para else sentence
        if len(candidate) < min_length:
            current_para = candidate
        else:
            paragraphs.append(candidate.strip())
            current_para = ""
    if current_para:
        paragraphs.append(current_para.strip())
    paragraphs = [p for p in paragraphs if p]

    # A run with no sentence breaks (an unpunctuated transcript) buckets into
    # one oversized paragraph above; hard-split anything well over target into
    # word windows so it stays readable and embeddable.
    hard_cap = min_length * 2
    bounded = []
    for para in paragraphs:
        if len(para) <= hard_cap:
            bounded.append(para)
            continue
        window = ""
        for word in para.split():
            cand = (window + " " + word) if window else word
            if len(cand) < min_length:
                window = cand
            else:
                bounded.append(cand)
                window = ""
        if window:
            bounded.append(window)
    return bounded


def split_transcript_to_paragraphs(text, min_length=PARAGRAPH_TARGET_LENGTH):
    """Return a list of plain-text paragraphs from a stored transcript.

    Verbatim copy of the web app's text.py::split_transcript_to_paragraphs.
    Strips ALL HTML with a single bleach pass, splitting on existing ``<p>``
    boundaries the markup carried (if any) before bleaching so they survive,
    otherwise sentence-buckets the prose. Keep in sync with the web app.
    """
    if not text:
        return []
    raw = str(text)
    if "<p" in raw:
        chunks = []
        for chunk in raw.split("</p>"):
            cleaned = bleach.clean(chunk, tags=[], strip=True)
            cleaned = _entity_unescape(cleaned).strip()
            if cleaned:
                chunks.append(cleaned)
        if chunks:
            return chunks
        # Fall through to sentence bucketing if the split produced nothing.
    plain = _entity_unescape(bleach.clean(raw, tags=[], strip=True))
    return _bucket_plain_paragraphs(plain, min_length=min_length)


def _embed_text(text):
    """Embed a single chunk via the bge-m3 Ollama. Raises on any failure.

    requests-based equivalent of the web app's services/embeddings.py::embed_text
    (which uses httpx + a query cache). Same HTTP contract: POST
    {OLLAMA_BASE_URL}/api/embeddings with {"model": "bge-m3", "prompt": text},
    read the float vector from the "embedding" key. Reads OLLAMA_BASE_URL and the
    model name (EMBED_MODEL, default bge-m3) from the environment.

    Unlike the web app's query path (which returns None and falls back to keyword
    search), this RAISES on failure: the corpus path must not silently drop a
    chunk, and the worker's try/except turns a raise into status='error'.
    """
    base = (os.environ.get("OLLAMA_BASE_URL") or "").rstrip("/")
    text = (text or "").strip()
    if not base:
        raise RuntimeError("OLLAMA_BASE_URL is not set; cannot reach the bge-m3 Ollama.")
    if not text:
        raise ValueError("_embed_text received empty text")

    model = os.environ.get("EMBED_MODEL", "bge-m3")
    resp = requests.post(
        base + "/api/embeddings",
        json={"model": model, "prompt": text},
        timeout=EMBED_TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    emb = resp.json().get("embedding")
    if not isinstance(emb, list) or not emb:
        raise RuntimeError("Ollama returned no embedding vector")
    if len(emb) != EMBED_DIM:
        # The web app rejects any chunk whose vector is not exactly EMBED_DIM,
        # so fail loudly here rather than shipping a vector it will 400 on.
        raise RuntimeError(
            f"Embedding has {len(emb)} dims, expected {EMBED_DIM}"
        )
    return emb


def embed_chunks(text):
    """Chunk a transcript and embed each chunk with bge-m3.

    Input — ``text``: one language's full transcription (the stored HTML/plain
    transcript). Splitting REPLICATES the web app's split_transcript_to_paragraphs
    so chunk boundaries match the corpus backfill.

    Return — ``[{"idx": int, "text": str, "embedding": [float x EMBED_DIM]}]``,
    one entry per kept chunk. ``idx`` is the paragraph's position in the original
    split (chunks under EMBED_MIN_CHARS are skipped, mirroring embed_sermons.py,
    so idx values may have gaps — this matches the corpus backfill, which keeps
    the original enumerate() index too).

    Raises on the first embed failure so the worker marks the job status='error'.
    Raises ValueError if the transcript yields no usable chunks.
    """
    paragraphs = split_transcript_to_paragraphs(text)
    chunks = []
    for idx, para in enumerate(paragraphs):
        para = (para or "").strip()
        if len(para) < EMBED_MIN_CHARS:
            continue
        embedding = _embed_text(para)
        chunks.append({"idx": idx, "text": para, "embedding": embedding})

    if not chunks:
        raise ValueError("embed_chunks produced no usable chunks from transcript")
    return chunks
