"""Authentication utilities for the Ember API."""

from __future__ import annotations

import hashlib
import os
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class APIKeyManager:
    """Manages API key generation and validation."""

    vault_dir: Path
    _cached_key: Optional[str] = None

    @property
    def key_file_path(self) -> Path:
        """Path to the stored API key file."""
        return self.vault_dir / "config" / ".api_key"

    def get_or_generate_key(self) -> str:
        """Get existing API key or generate a new one."""
        if self._cached_key:
            return self._cached_key

        # Try to load from file
        if self.key_file_path.exists():
            try:
                key = self.key_file_path.read_text(encoding="utf-8").strip()
                if key:
                    self._cached_key = key
                    return key
            except OSError:
                pass

        # Generate new key
        key = self._generate_key()
        self._save_key(key)
        self._cached_key = key
        return key

    def validate_key(self, provided_key: str) -> bool:
        """Validate a provided API key."""
        if not provided_key:
            return False

        stored_key = self.get_or_generate_key()
        # Use constant-time comparison to prevent timing attacks
        return secrets.compare_digest(provided_key, stored_key)

    def regenerate_key(self) -> str:
        """Generate a new API key, replacing any existing one."""
        key = self._generate_key()
        self._save_key(key)
        self._cached_key = key
        return key

    def _generate_key(self) -> str:
        """Generate a secure random API key."""
        # Generate 32 bytes of random data and encode as hex (64 chars)
        return secrets.token_hex(32)

    def _save_key(self, key: str) -> None:
        """Save the API key to the vault config directory."""
        try:
            self.key_file_path.parent.mkdir(parents=True, exist_ok=True)
            self.key_file_path.write_text(key, encoding="utf-8")
            # Set restrictive permissions (owner read/write only)
            self.key_file_path.chmod(0o600)
        except OSError:
            pass  # Fail silently; key is still cached in memory


def hash_key(key: str) -> str:
    """Create a one-way hash of an API key for logging/comparison."""
    return hashlib.sha256(key.encode()).hexdigest()[:16]


__all__ = ["APIKeyManager", "hash_key"]
