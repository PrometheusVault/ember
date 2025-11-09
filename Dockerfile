# Dockerfile - Ember dev environment
FROM python:3.11-slim

# System dependencies
RUN apt-get update && apt-get install -y \
    recoll \
    taskwarrior \
    tmux \
    zsh \
    sqlite3 \
    build-essential \
    cmake \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create app user
RUN useradd -ms /bin/bash ember
USER ember

WORKDIR /opt/ember-app

ENV VAULT_DIR=/vault
ENV PYTHONUNBUFFERED=1

# Create a virtualenv inside the container
RUN python -m venv /opt/ember-app/venv

# Install Python deps from requirements.txt if present
COPY --chown=ember:ember requirements.txt* ./
RUN . /opt/ember-app/venv/bin/activate && \
    pip install --upgrade pip && \
    if [ -f requirements.txt ]; then pip install -r requirements.txt; fi

# Default command: keep container alive; we attach with docker exec
CMD ["sleep", "infinity"]
