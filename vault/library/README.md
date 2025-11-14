# Vault Library

This directory is *persistent storage* for every reference guide Ember should
use when answering prompts. Anything you place here (or in subdirectories such
as `notes/`, `almanac/`, `knowledge/`) survives upgrades because the entire
`$VAULT_DIR` lives outside the repo checkout.

Usage tips:

- Drop Markdown (`.md`, `.markdown`) or plaintext (`.txt`) documents you can
  safely share with llama.cpp. Think field manuals, foraging guides, medical
  quick references, radio SOPs, or your own almanac entries.
- Ember reads up to ~2 KB per file at startup. Split massive books into
  chapters so high-value sections are more likely to fit.
- Organize by topic. Subdirectories are supported and keep search manageable.
- When you add or edit files, restart Ember so the documentation cache reloads.

Remember: this vault directory is the canonical, long-lived source of truth.
Treat the repo copy (`reference/` etc.) as optional seed data; keep *your*
growing knowledge base here.***
