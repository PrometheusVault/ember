# Makefile for ember dev environment

# ---- Config -----------------------------------------------------------------

IMAGE_NAME      ?= ember-dev
IMAGE_TAG       ?= latest
CONTAINER_NAME  ?= ember-dev
DOCKERFILE      ?= Dockerfile

# Path inside the container where the project is mounted
WORKDIR         ?= /srv/ember
PROJECT_ROOT    := $(shell pwd)

# Map host user into container so created files aren't owned by root
UID             := $(shell id -u)
GID             := $(shell id -g)

# Default port mappings (override with `make dev PORTS="..."`)
PORTS           ?= -p 3000:3000

# Extra env vars passed to `docker run`, e.g. ENV_VARS="-e FOO=bar -e BAZ=qux"
ENV_VARS        ?=

# Command used for tests inside the running container
TEST_CMD        ?= pytest

# Optional model path used by `make repl` (inside the container)
MODEL           ?=

REPL_EXPORT_ENV :=
ifneq ($(strip $(MODEL)),)
REPL_EXPORT_ENV += export LLAMA_CPP_MODEL='$(MODEL)'; 
endif
ifneq ($(strip $(LLAMA_CPP_MAX_TOKENS)),)
REPL_EXPORT_ENV += export LLAMA_CPP_MAX_TOKENS='$(LLAMA_CPP_MAX_TOKENS)'; 
endif
ifneq ($(strip $(LLAMA_CPP_TEMPERATURE)),)
REPL_EXPORT_ENV += export LLAMA_CPP_TEMPERATURE='$(LLAMA_CPP_TEMPERATURE)'; 
endif
ifneq ($(strip $(LLAMA_CPP_TOP_P)),)
REPL_EXPORT_ENV += export LLAMA_CPP_TOP_P='$(LLAMA_CPP_TOP_P)'; 
endif
ifneq ($(strip $(LLAMA_CPP_TIMEOUT)),)
REPL_EXPORT_ENV += export LLAMA_CPP_TIMEOUT='$(LLAMA_CPP_TIMEOUT)'; 
endif
ifneq ($(strip $(LLAMA_CPP_THREADS)),)
REPL_EXPORT_ENV += export LLAMA_CPP_THREADS='$(LLAMA_CPP_THREADS)'; 
endif
ifneq ($(strip $(LLAMA_CPP_BIN)),)
REPL_EXPORT_ENV += export LLAMA_CPP_BIN='$(LLAMA_CPP_BIN)'; 
endif
ifneq ($(strip $(LLAMA_CPP_MODEL_DIR)),)
REPL_EXPORT_ENV += export LLAMA_CPP_MODEL_DIR='$(LLAMA_CPP_MODEL_DIR)'; 
endif

.DEFAULT_GOAL := help

# ---- Targets ----------------------------------------------------------------

.PHONY: help build rebuild dev run shell repl logs stop rm restart ps prune test exec

help: ## Show this help message
	@echo "Ember dev Makefile"
	@echo
	@echo "Usage:"
	@echo "  make build        Build the dev image"
	@echo "  make rebuild      Rebuild the dev image without cache"
	@echo "  make dev          Start dev container (detached) with volume mount"
	@echo "  make run          Run container in foreground (one-off)"
	@echo "  make shell        Open an interactive shell in the running container"
	@echo "  make repl         Start (if needed) and attach to the Ember REPL inside the container"
	@echo "  make exec CMD=... Exec a command in the running container"
	@echo "  make logs         Follow container logs"
	@echo "  make test         Run tests inside the running container"
	@echo "  make stop         Stop the dev container"
	@echo "  make rm           Remove the dev container"
	@echo "  make restart      Restart the dev container"
	@echo "  make ps           Show ember-related containers"
	@echo "  make prune        Remove stopped ember containers"
	@echo
	@echo "Configurable vars (override like VAR=value make dev):"
	@echo "  IMAGE_NAME      ($(IMAGE_NAME))"
	@echo "  IMAGE_TAG       ($(IMAGE_TAG))"
	@echo "  CONTAINER_NAME  ($(CONTAINER_NAME))"
	@echo "  WORKDIR         ($(WORKDIR))"
	@echo "  PORTS           ($(PORTS))"
	@echo "  ENV_VARS        ($(ENV_VARS))"
	@echo "  TEST_CMD        ($(TEST_CMD))"
	@echo "  MODEL           (make repl) path inside container to GGUF, e.g. MODEL=/srv/ember/models/foo.gguf"
	@echo "  LLAMA_CPP_*     (make repl) e.g. LLAMA_CPP_MAX_TOKENS=64 LLAMA_CPP_TIMEOUT=180"

build: ## Build the dev image
	docker build \
		-f $(DOCKERFILE) \
		-t $(IMAGE_NAME):$(IMAGE_TAG) \
		.

rebuild: ## Rebuild the dev image without using cache
	docker build \
		--no-cache \
		-f $(DOCKERFILE) \
		-t $(IMAGE_NAME):$(IMAGE_TAG) \
		.

dev: ## Start dev container (detached) with source mounted
	docker run -d --rm \
		--name $(CONTAINER_NAME) \
		$(PORTS) \
		-v $(PROJECT_ROOT):$(WORKDIR) \
		-w $(WORKDIR) \
		-e HOST_UID=$(UID) \
		-e HOST_GID=$(GID) \
		$(ENV_VARS) \
		$(IMAGE_NAME):$(IMAGE_TAG)

run: ## Run container in foreground (good for CI or quick checks)
	docker run --rm \
		--name $(CONTAINER_NAME) \
		$(PORTS) \
		-v $(PROJECT_ROOT):$(WORKDIR) \
		-w $(WORKDIR) \
		-e HOST_UID=$(UID) \
		-e HOST_GID=$(GID) \
		$(ENV_VARS) \
		$(IMAGE_NAME):$(IMAGE_TAG)

shell: ## Open an interactive shell in the running container
	docker exec -it $(CONTAINER_NAME) /bin/bash

repl: ## Attach to the Ember REPL inside the dev container (starts container if needed)
	@if ! docker ps --format '{{.Names}}' | grep -q '^$(CONTAINER_NAME)$$'; then \
		echo "Container $(CONTAINER_NAME) is not running. Starting via 'make dev'..."; \
		$(MAKE) dev; \
		sleep 2; \
	fi
	docker exec -it $(CONTAINER_NAME) sh -lc "$(REPL_EXPORT_ENV). /opt/ember-app/venv/bin/activate && cd $(WORKDIR) && python -m ember"

exec: ## Exec an arbitrary command in the running container (CMD=\"...\")
	@if [ -z "$(CMD)" ]; then \
		echo "Usage: make exec CMD='your command here'"; \
		exit 1; \
	fi
	docker exec -it $(CONTAINER_NAME) sh -lc "$(CMD)"

logs: ## Follow container logs
	docker logs -f $(CONTAINER_NAME)

test: ## Run tests inside the running container
	docker exec -it $(CONTAINER_NAME) sh -lc "$(TEST_CMD)"

stop: ## Stop the dev container
	-@docker stop $(CONTAINER_NAME) >/dev/null 2>&1 || true

rm: stop ## Remove the dev container (after stopping)
	-@docker rm $(CONTAINER_NAME) >/dev/null 2>&1 || true

restart: stop dev ## Restart the dev container

ps: ## Show ember-related containers
	docker ps -a --filter "name=$(CONTAINER_NAME)"

prune: ## Remove all stopped ember containers
	-docker ps -a --filter "name=$(CONTAINER_NAME)" --filter "status=exited" -q | xargs -r docker rm
