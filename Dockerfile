# syntax=docker/dockerfile:1.7
#
# The app shells out to the Claude Code CLI, so Node and the CLI are runtime
# dependencies, not build-time ones.
#
# Moved python:3.12-slim -> python:3.13-alpine. Two things made that possible:
# the Python dependency set (Flask, requests, bleach) is pure Python, and the
# Claude Code CLI runs correctly on musl - its vendored ripgrep loads under
# Alpine, verified before this change.
#
# Node now comes from apk rather than an unpacked tarball. The tarball was
# pinned to a version that only receives updates when someone edits this file,
# and its URL was hardcoded to linux-x64, which silently broke arm64 builds.
# The apk package tracks Alpine's security updates and is multi-arch.

# ---- Stage 1: build the Python virtualenv ----
FROM python:3.13-alpine AS python-build

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PATH="/opt/venv/bin:$PATH"

RUN apk add --no-cache build-base libffi-dev openssl-dev

RUN python -m venv /opt/venv

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# ---- Stage 2: install the Claude Code CLI ----
FROM python:3.13-alpine AS node-build

RUN apk add --no-cache nodejs npm libstdc++

# Install Claude Code CLI into a staging prefix so the runtime stage can copy
# it without also inheriting npm and its cache.
ARG CLAUDE_CLI_CACHE_BUST=1
RUN npm install -g --prefix /opt/node-cli @anthropic-ai/claude-code \
    && PATH="/opt/node-cli/bin:$PATH" claude --version

# ---- Stage 3: runtime ----
FROM python:3.13-alpine

LABEL org.opencontainers.image.source="https://github.com/jaycollett/AISermonDataAPI"
LABEL org.opencontainers.image.description="AI sermon analysis API backed by the Claude Code CLI"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    FLASK_APP=app.py \
    FLASK_RUN_HOST=0.0.0.0 \
    FLASK_RUN_PORT=5090 \
    CLAUDE_CONFIG_DIR=/data/claude-home \
    PATH="/opt/venv/bin:/opt/node-cli/bin:$PATH"

# nodejs is the CLI's interpreter; npm is deliberately left out of the runtime.
# ca-certificates backs the outbound HTTPS both the CLI and the app make.
RUN apk add --no-cache nodejs ca-certificates libffi openssl libstdc++

COPY --from=python-build /opt/venv /opt/venv
COPY --from=node-build /opt/node-cli /opt/node-cli

WORKDIR /app

# Application source.
COPY . .

# /data is mounted from a PVC in K8S and holds the Claude Code CLI state
# (OAuth credentials, session cache). Pre-create it so the directory exists
# even if no PVC is mounted (e.g. local docker run). It must be writable by
# the non-root runtime user, which is also why $HOME points at it.
ENV HOME=/data/claude-home
RUN addgroup -g 1000 -S appuser \
    && adduser -u 1000 -S -G appuser -H -s /sbin/nologin appuser \
    && mkdir -p /data/claude-home \
    && chown -R appuser:appuser /app /data

USER 1000:1000

EXPOSE 5090

CMD ["python", "app.py"]
