# AGENTS.md
> Operational and Context Map for the **Ember** Repository
> Project Lead: Joshua Estes (@matrix)
> Repository: `ember`
> Context: Core runtime environment for the Prometheus Vault ecosystem

---

## 🧠 Overview

The **Ember** project represents the *runtime layer* for the Prometheus Vault platform — responsible for provisioning, executing, and managing distributed components on lightweight edge or embedded systems (e.g., Raspberry Pi).

This file defines all active **agents**, their **responsibilities**, and **interfaces** to maintain system clarity and interoperability across environments.

---

## ⚙️ System Architecture Summary

- **Core Function:** Bootstraps and manages the runtime environment
- **Mode:** Headless or attached UI mode
- **Runtime Environment:** Linux (bare metal or containerized)
- **Primary Interface:** CLI and local web interface
- **Deployment Contexts:**
  - `dev` → Docker containerized (make + docker)
  - `prod` → Bare metal, auto-start on boot
- **Goal:** Provide an extensible, self-provisioning environment capable of executing additional tools ("agents") modularly.

---

## 🗂️ Agent Registry

All agents register themselves with a central registry (`ember/agents/registry.py`).
At startup the registry evaluates two things before an agent runs:

1. **Enablement** – Controlled via configuration:
   ```yaml
   agents:
     enabled:
       - provision.agent
       - network.agent
     disabled:
       - update.agent
   ```
   If `agents.enabled` is provided, only names in that list run. Otherwise every
   agent defaults to its own `default_enabled` flag unless it appears in
   `agents.disabled`.
2. **Readiness** – Agents marked `requires_ready=True` automatically skip when
   the configuration bundle is still `missing`/`invalid`.

Each agent contributes metadata (name, description, triggers, handler) so it can
be inspected via `/status` or extended later by plugin loaders.

### Inspecting agent state

- `/agents` – REPL command that displays every registered agent, whether it is
  currently enabled, plus the latest result recorded by the registry.
- `/status` – Includes the latest run data under the “Agents” panel alongside
  other diagnostics.

---

## 👥 Agents

Each agent is defined by:
- **Role:** What it does.
- **Responsibility:** Core purpose or scope.
- **Triggers:** When and how it activates.
- **Inputs / Outputs:** Data flow or communication channels.
- **Dependencies:** Other agents, services, or configurations.

---

### 🔥 1. `core.agent`

**Role:** System Orchestrator
**Responsibility:** Boot, monitor, and restart the Ember runtime environment.
**Triggers:** System startup, watchdog signals, or manual invocation.
**Inputs:** `config/system.yml`, system state
**Outputs:** Runtime logs, status signals
**Dependencies:** `network.agent`, `provision.agent`

---

### 🌐 2. `network.agent`

**Role:** Network Manager
**Responsibility:** Detects, configures, and maintains local network connectivity for Ember and dependent modules.
**Triggers:** Boot, interface changes, manual refresh
**Inputs:** OS network interfaces, `network.yml`
**Outputs:** Active IP, routes, DNS info (`/agents` exposes `primary_interface`, interface inventory, DNS sources, and connectivity checks)
**Dependencies:** None

**Developer notes:** Configure behavior under the `network` block in `config/system.yml` or a vault override. Keys include:

```yaml
network:
  enabled: true
  preferred_interfaces:
    - eth0
    - wlan0
  include_loopback: false
  connectivity_checks:
    - 1.1.1.1:53
  connectivity_timeout: 1.0
  dns_paths:
    - /etc/resolv.conf
```

- When `preferred_interfaces` is populated the agent prioritizes those names when reporting `primary_interface` to the REPL and `/status`.
- `connectivity_checks` are optional host[:port] probes (TCP) so offline nodes never block; leave empty on fully air-gapped rigs.

**Operator notes:** Run `/agents` or `/status` to confirm `network.agent` sees at least one `is_up` interface. The result includes:

- Interface list with IPv4/IPv6/MAC records so you can copy addresses without leaving the REPL.
- DNS sources from the configured `dns_paths` so you know which resolver file is active.
- Connectivity summary (`connectivity n/m targets`) to validate WAN reachability before triggering updates or tool downloads.

If networking is intentionally unavailable, leave the agent enabled so dependent services see an explicit “degraded” status, or add it to `agents.disabled` for that node.

---

### 🧰 3. `provision.agent`

**Role:** Environment Provisioner
**Responsibility:** Handles first-boot setup, installs dependencies, and provisions the runtime environment.
**Triggers:** Boot or configuration change
**Inputs:** `setup.yml`, environment variables
**Outputs:** Installed packages, configuration logs
**Dependencies:** `network.agent`

---

### 🧩 4. `toolchain.agent`

**Role:** Developer Tool Manager
**Responsibility:** Ensures all development tools (Docker, Make, git hooks, language runtimes) are installed and version-aligned.
**Triggers:** Manual (`make build` or `make dev`)
**Inputs:** `Makefile`, `.toolchain.yml`
**Outputs:** Ready-to-use local dev environment
**Dependencies:** `provision.agent`

---

### 🧪 5. `test.agent`

**Role:** Continuous Verification
**Responsibility:** Runs tests, linting, and environment checks.
**Triggers:** CI/CD or `make test`
**Inputs:** `tests/`, `Makefile`, `.env`
**Outputs:** Test reports, exit codes
**Dependencies:** `toolchain.agent`

---

### 🧭 6. `update.agent`

**Role:** System Updater
**Responsibility:** Fetches and applies updates to Ember or toolchains.
**Triggers:** Manual or scheduled
**Inputs:** Remote repo metadata
**Outputs:** Updated binaries or configs
**Dependencies:** `network.agent`, `core.agent`

---

### 🧩 7. `plugin.agent`

**Role:** Extension Loader
**Responsibility:** Loads and manages additional modules (“tools”) dynamically without requiring manual reference changes in core code.
**Triggers:** Boot or tool registration event
**Inputs:** `/plugins` directory or `/usr/local/ember/plugins`
**Outputs:** Registered runtime extensions
**Dependencies:** `core.agent`

---

## 🧬 File and Directory Conventions

| Path | Description |
|------|--------------|
| `/Makefile` | Standardized dev commands |
| `/agents/` | Each agent’s implementation or wrapper |
| `/config/` | YAML configuration files for environment & tools |
| `/scripts/` | Provision and maintenance scripts |
| `/plugins/` | External or optional tools |
| `/logs/` | Runtime logs |
| `/tests/` | Verification suites |

---

## 🧠 Command Context Map

| Command | Description | Agent |
|----------|--------------|--------|
| `make build` | Build container image | `toolchain.agent` |
| `make dev` | Run dev container | `core.agent` |
| `make shell` | Open shell in container | `toolchain.agent` |
| `make test` | Run test suite | `test.agent` |
| `make prune` | Clean old containers | `core.agent` |
| `make update` | (Future) Auto-update Ember | `update.agent` |

---

## 🔒 Security Principles

- **Least Privilege:** Each agent runs under minimal permissions.
- **Isolation:** Agents communicate via local IPC or message queues, not shared globals.
- **Integrity Checks:** Toolchain and update agents verify checksums/signatures before install.
- **Auditing:** Logs stored under `/logs/agents/<agent>.log`.

---

## 🧭 Future Agents (Planned)

| Agent | Purpose |
|--------|----------|
| `metrics.agent` | Collects system performance and telemetry |
| `ui.agent` | Provides optional web-based dashboard for local monitoring |
| `auth.agent` | Manages keys, tokens, and secure communication |
| `registry.agent` | Discovers and registers new tools or nodes in the Ember cluster |

---

## 🪶 Notes

- All agents are **loosely coupled** and **self-describing** — configuration is declarative via YAML, not hardcoded imports.
- Agents communicate using a standardized JSON protocol or message bus (TBD).
- Design aims to make Ember capable of functioning as a **self-provisioning edge node** with minimal human intervention.

---

## 🧰 Maintainer Commands

```bash
# Start dev environment
make dev

# Access running container
make shell

# Run tests
make test

# Stop everything
make stop
