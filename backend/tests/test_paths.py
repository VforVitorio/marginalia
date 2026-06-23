"""Path suggestions (#46): Obsidian vault detection + scan-folder suggestions."""

from __future__ import annotations

import json

import marginalia.paths as paths


def test_detect_vaults_sorts_newest_first_and_skips_missing(tmp_path, monkeypatch) -> None:
    old = tmp_path / "OldVault"
    new = tmp_path / "NewVault"
    old.mkdir()
    new.mkdir()
    config = tmp_path / "obsidian.json"
    config.write_text(
        json.dumps(
            {
                "vaults": {
                    "a": {"path": str(old), "ts": 100},
                    "b": {"path": str(new), "ts": 200},
                    "gone": {"path": str(tmp_path / "Deleted"), "ts": 300},  # not on disk
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(paths, "_obsidian_config_path", lambda: config)

    assert paths.detect_obsidian_vaults() == [str(new), str(old)]


def test_detect_vaults_empty_when_no_config(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(paths, "_obsidian_config_path", lambda: tmp_path / "missing.json")
    assert paths.detect_obsidian_vaults() == []


def test_suggest_scan_folders_only_existing(tmp_path, monkeypatch) -> None:
    (tmp_path / "Dropbox").mkdir()
    (tmp_path / "Documents").mkdir()
    # "OneDrive" intentionally absent → must not appear.
    monkeypatch.setattr(paths.Path, "home", lambda: tmp_path)

    found = paths.suggest_scan_folders()

    assert str(tmp_path / "Dropbox") in found
    assert str(tmp_path / "Documents") in found
    assert str(tmp_path / "OneDrive") not in found
    assert len(found) == len(set(found))  # deduped
