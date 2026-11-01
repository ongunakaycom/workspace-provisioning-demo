# syntax=docker/dockerfile:1

FROM python:3.12-slim

WORKDIR /app

# Create a non-root user
RUN useradd -m -u 1001 -s /bin/bash provisioner

# Copy files and change ownership in ONE step (much faster)
COPY --chown=provisioner:provisioner provisioner/ ./provisioner/
COPY --chown=provisioner:provisioner data/ ./data/

USER provisioner

ENTRYPOINT ["python", "-m", "provisioner.cli"]
CMD ["--help"]