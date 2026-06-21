"""Checks de la fundación: el seam OCREngine se mantiene y la config hace roundtrip."""

from collections.abc import AsyncIterator

from marginalia.config import Settings, load_settings, save_settings
from marginalia.ocr.engine import EngineInfo, OCREngine


class _FakeEngine:
    """Engine mínimo que debe cumplir el Protocol estructuralmente."""

    info = EngineInfo(id="fake", display_name="Fake", kind="local", current_model="m")

    def models(self) -> list[str]:
        return ["m"]

    async def transcribe_page(self, image_png: bytes, prompt: str) -> AsyncIterator[str]:
        yield "hola"


def test_fake_engine_satisfies_protocol() -> None:
    engine = _FakeEngine()
    assert isinstance(engine, OCREngine)
    assert engine.info.kind == "local"


def test_settings_roundtrip(tmp_path) -> None:
    path = tmp_path / "settings.json"
    save_settings(Settings(vault_path="/vault", strategies=["mirror", "wikilinks"]), path)
    loaded = load_settings(path)
    assert loaded.vault_path == "/vault"
    assert "wikilinks" in loaded.strategies


def test_load_settings_defaults_when_missing(tmp_path) -> None:
    loaded = load_settings(tmp_path / "nope.json")
    assert loaded.strategies == ["mirror"]
    assert loaded.vault_path is None
