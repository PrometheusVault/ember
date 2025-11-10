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
    pkg-config \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Build llama.cpp so Ember can call it within the container
RUN git clone --depth=1 https://github.com/ggerganov/llama.cpp.git /opt/llama.cpp && \
    cd /opt/llama.cpp && \
    cmake -B build -DLLAMA_CURL=OFF && \
    cmake --build build --config Release -j"$(nproc)" && \
    #make -j"$(nproc)" llama-cli && \
    mkdir -p /opt/llama.cpp/models

# Create app user
RUN useradd -ms /bin/bash ember
RUN chown -R ember:ember /opt/llama.cpp
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
