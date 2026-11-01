# syntax=docker/dockerfile:1

FROM python:3.12-slim

WORKDIR /app

# Create a non-root user (Security Best Practice)
RUN useradd -m -u 1001 -s /bin/bash provisioner

# Copy application code directly
COPY provisioner/ ./provisioner/
COPY data/ ./data/

# Ensure the non-root user owns the app directory
RUN chown -R provisioner:provisioner /app

USER provisioner

ENTRYPOINT ["python", "-m", "provisioner.cli"]
CMD ["--help"]