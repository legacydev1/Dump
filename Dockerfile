# ─────────────────────────────────────────────────────────────
#  Telegram Log Search Bot — Dockerfile
#  Multi-stage build: slim final image, non-root user.
# ─────────────────────────────────────────────────────────────

# ── Stage 1: dependency builder ───────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# System deps needed to compile some wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip \
 && pip install --prefix=/install --no-cache-dir -r requirements.txt


# ── Stage 2: runtime image ────────────────────────────────────
FROM python:3.11-slim AS runtime

# Metadata
LABEL maintainer="LOGSBOT"
LABEL description="Telegram Log Search Bot (aiogram 3.x + SQLite FTS5)"

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Create non-root user for security
RUN groupadd --gid 1001 botuser \
 && useradd  --uid 1001 --gid botuser --shell /bin/bash --create-home botuser

# App directory
WORKDIR /app

# Copy source code
COPY . .

# Create persistent data directories and set ownership
RUN mkdir -p data/uploads \
 && chown -R botuser:botuser /app

# Switch to non-root user
USER botuser

# SQLite DB and uploads are stored in /app/data (mount a volume here)
VOLUME ["/app/data"]

# Health-check: verify Python can import the bot
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import aiogram, aiosqlite; print('OK')" || exit 1

# Single entry point
CMD ["python", "main.py"]
