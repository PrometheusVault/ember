from pathlib import Path

from ember.configuration import load_runtime_configuration


def _write_override(vault: Path, content: str) -> None:
    cfg_dir = vault / "config"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    (cfg_dir / "local.yml").write_text(content)


def test_invalid_types_raise_diagnostics(tmp_path: Path):
    vault = tmp_path / "vault"
    vault.mkdir()
    _write_override(
        vault,
        """
        runtime:
          auto_restart: "yes"
        """,
    )

    bundle = load_runtime_configuration(vault)

    assert bundle.status == "invalid"
    assert any("auto_restart" in diag.message for diag in bundle.diagnostics)


def test_unknown_keys_warn(tmp_path: Path):
    vault = tmp_path / "vault"
    vault.mkdir()
    _write_override(
        vault,
        """
        mystery:
          value: 1
        """,
    )

    bundle = load_runtime_configuration(vault)

    assert any("Unknown configuration key" in diag.message for diag in bundle.diagnostics)
