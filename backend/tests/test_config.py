"""Durable-persistence coverage for config.py: MARGINALIA_HOME anchoring and atomic writes (#143).

Covers BE-11 (CWD-relative paths silently misbehaving when run from elsewhere) and BE-12 (a
crash mid-write corrupting settings.json into an unhandled 500). test_skeleton.py already covers
the plain Settings round-trip; this file is additive, not a replacement.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from marginalia import config
from marginalia.config import Settings, save_settings


def test_resolve_home_dir_none_when_unset() -> None:
    """Unset/empty env value means "stay CWD-relative" — the historical default."""
    assert config._resolve_home_dir(None) is None
    assert config._resolve_home_dir("") is None


def test_resolve_home_dir_anchors_to_given_value() -> None:
    assert config._resolve_home_dir("/opt/marginalia") == Path("/opt/marginalia")


def test_resolve_paths_stays_cwd_relative_when_home_is_none() -> None:
    """No MARGINALIA_HOME → paths stay relative, exactly like before the env var existed.

    This is the contract backend/tests/test_api.py leans on via monkeypatch.chdir(tmp_path).
    """
    data_dir, settings_path, providers_path = config._resolve_paths(None)
    assert data_dir == Path("data")
    assert settings_path == Path("data/settings.json")
    assert providers_path == Path("providers.toml")
    assert not data_dir.is_absolute()
    assert not providers_path.is_absolute()


def test_resolve_paths_anchors_under_home_when_set() -> None:
    home = Path("/srv/marginalia")
    data_dir, settings_path, providers_path = config._resolve_paths(home)
    assert data_dir == home / "data"
    assert settings_path == home / "data" / "settings.json"
    assert providers_path == home / "providers.toml"


def test_marginalia_home_env_anchors_module_constants(tmp_path, monkeypatch) -> None:
    """Integration check: setting MARGINALIA_HOME re-anchors the live module constants.

    Reloads marginalia.config so the module-level DATA_DIR/SETTINGS_PATH/PROVIDERS_PATH pick up
    the env var, then restores the default (unset) state so no other test observes the change —
    other modules already hold their own references from earlier imports, so this reload cannot
    leak into them, but restoring keeps marginalia.config itself back to its default shape.
    """
    monkeypatch.setenv("MARGINALIA_HOME", str(tmp_path))
    try:
        importlib.reload(config)
        assert tmp_path / "data" == config.DATA_DIR
        assert tmp_path / "data" / "settings.json" == config.SETTINGS_PATH
        assert tmp_path / "providers.toml" == config.PROVIDERS_PATH
    finally:
        monkeypatch.delenv("MARGINALIA_HOME", raising=False)
        importlib.reload(config)


def test_write_text_atomic_writes_full_content(tmp_path) -> None:
    target = tmp_path / "settings.json"
    config.write_text_atomic(target, '{"a": 1}')
    assert target.read_text(encoding="utf-8") == '{"a": 1}'
    assert list(tmp_path.iterdir()) == [target]  # no leftover .tmp file


def test_write_text_atomic_overwrites_existing_file(tmp_path) -> None:
    target = tmp_path / "settings.json"
    target.write_text('{"a": 1}', encoding="utf-8")
    config.write_text_atomic(target, '{"a": 2}')
    assert target.read_text(encoding="utf-8") == '{"a": 2}'


def test_write_text_atomic_leaves_original_untouched_on_failed_write(tmp_path, monkeypatch) -> None:
    """A crash/error mid-write must not truncate the real file (BE-12)."""
    target = tmp_path / "settings.json"
    target.write_text('{"a": 1}', encoding="utf-8")
    tmp_target = target.with_name(f"{target.name}.tmp")

    original_write_text = Path.write_text

    def _boom(self: Path, *args: object, **kwargs: object) -> int:
        if self == tmp_target:
            raise OSError("disk full")
        return original_write_text(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "write_text", _boom)

    with pytest.raises(OSError, match="disk full"):
        config.write_text_atomic(target, '{"a": 2}')

    monkeypatch.undo()
    assert target.read_text(encoding="utf-8") == '{"a": 1}'  # untouched, not truncated


def test_save_settings_uses_atomic_write_no_tmp_left_behind(tmp_path) -> None:
    path = tmp_path / "settings.json"
    save_settings(Settings(vault_path="/vault"), path)
    assert path.exists()
    assert not (tmp_path / "settings.json.tmp").exists()
