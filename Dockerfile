# syntax=docker/dockerfile:1

# ---------- Stage 1: Build / dependency resolution ----------
FROM python:3.12-slim AS builder
WORKDIR /app

# No dependencies to install (stdlib only), but this stage
# is where you would add `pip install -r requirements.txt`
COPY provisioner/ ./provisioner/
COPY data/ ./data/

# ---------- Stage 2: Runtime (hardened) ----------
FROM python:3.12-slim AS runtime
WORKDIR /app

# Non-root user (security best practice)
RUN useradd -m -u 1001 -s /bin/bash provisioner

# Copy application code with correct ownership
COPY --chown=provisioner:provisioner provisioner/ ./provisioner/
COPY --chown=provisioner:provisioner data/ ./data/

USER provisioner

ENTRYPOINT ["python", "-m", "provisioner.cli"]
CMD ["--help"]