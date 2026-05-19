# =============================================================================
# LateD backend — production container image (online detection)
# =============================================================================
#
# PURPOSE
# -------
# Build a minimal, hardened image that runs the supervision API + WebSocket
# server plus the online detection workers.
#
# DESIGN
# ------
# - Multi-stage: builder installs deps, final image only carries the wheel.
# - Runs as non-root user (uid 1000).
# - Read-only filesystem-friendly (writable paths: /data only).
# - No training stack inside this image — reduces attack surface.
#
# RUNTIME ROLE
# ------------
# This image is the central detection node. It receives canonical flows from
# upstream collectors, runs TGNN inference + recon detection, correlates,
# and serves the SOC dashboard over REST + WebSocket.
# =============================================================================

# --- builder stage -----------------------------------------------------------
FROM python:3.11-slim AS builder

WORKDIR /build

# System packages required to compile certain wheels (scapy/psycopg) — these
# are dropped from the final image.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libpq-dev libpcap-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --prefix=/install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY pyproject.toml .
RUN pip install --prefix=/install --no-cache-dir .

# --- final stage -------------------------------------------------------------
FROM python:3.11-slim

# Runtime-only OS packages (libpcap for scapy live capture — opt-in only).
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 libpcap0.8 && \
    rm -rf /var/lib/apt/lists/* && \
    useradd --uid 1000 --create-home --shell /bin/bash lated

COPY --from=builder /install /usr/local

WORKDIR /app
COPY --chown=lated:lated src/ ./src/
COPY --chown=lated:lated config/ ./config/

USER lated
ENV PYTHONPATH=/app/src
ENV LATED_ENV=production
EXPOSE 8000

# The default command runs the supervision API.
# Detection workers can be launched in separate containers using `lated-online`.
CMD ["lated-api"]
