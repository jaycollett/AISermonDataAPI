# syntax=docker/dockerfile:1
FROM python:3.12-slim

LABEL org.opencontainers.image.source="https://github.com/jaycollett/AISermonDataAPI"
LABEL org.opencontainers.image.description="AI sermon analysis API backed by the Claude Code CLI"

ENV PYTHONUNBUFFERED=1 \
    FLASK_APP=app.py \
    FLASK_RUN_HOST=0.0.0.0 \
    FLASK_RUN_PORT=5090 \
    CLAUDE_CONFIG_DIR=/data/claude-home

# System packages: curl + ca-certificates for the Node tarball download.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js (official tarball pinned to match AutoInvestor reference).
ARG NODE_VERSION=22.14.0
RUN curl -fsSL https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-x64.tar.gz \
    | tar -xz --strip-components=1 -C /usr/local

# Install Claude Code CLI globally via npm. Lands at /usr/local/bin/claude.
ARG CLAUDE_CLI_CACHE_BUST=1
RUN npm install -g @anthropic-ai/claude-code \
    && claude --version

WORKDIR /app

# Python deps first for layer caching.
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Application source.
COPY . .

# /data is mounted from a PVC in K8S and holds the Claude Code CLI state
# (OAuth credentials, session cache). Pre-create it so the directory exists
# even if no PVC is mounted (e.g. local docker run).
RUN mkdir -p /data/claude-home

EXPOSE 5090

CMD ["python", "app.py"]
