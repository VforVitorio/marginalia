"""API flow: settings, create-from-upload, fetch, page image, edit, export, and the OCR stream."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from pathlib import Path

import pymupdf
from fastapi.testclient import TestClient

from marginalia.api.deps import get_active_engine
from marginalia.api.main import app
from marginalia.config import CLOUD_MODELS
from marginalia.ocr.engine import EngineInfo


class _FakeEngine:
    info = EngineInfo(id="fake", display_name="Fake", kind="local", current_model="m")

    def models(self) -> list[str]:
        return ["m"]

    async def transcribe_page(self, image_png: bytes, prompt: str) -> AsyncIterator[str]:
        yield "transcribed"


def _one_page_pdf() -> bytes:
    doc = pymupdf.open()
    doc.new_page()
    data = doc.tobytes()
    doc.close()
    return data


def test_full_api_flow(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)  # isolate data/ and providers.toml under tmp
    client = TestClient(app)

    assert client.get("/api/settings").json()["strategies"] == ["mirror"]
    vault = str(tmp_path / "vault")
    assert client.put("/api/settings", json={"vault_path": vault}).json()["vault_path"] == vault

    created = client.post("/api/jobs", files={"file": ("notes.pdf", _one_page_pdf(), "application/pdf")}).json()
    job_id = created["job_id"]
    assert created["pages"] == 1

    job = client.get(f"/api/jobs/{job_id}").json()
    assert job["pages"][0]["image_url"].endswith(f"/api/jobs/{job_id}/pages/1/image")

    image = client.get(f"/api/jobs/{job_id}/pages/1/image")
    assert image.status_code == 200
    assert image.content.startswith(b"\x89PNG")

    client.put(f"/api/jobs/{job_id}/pages/1", json={"markdown": "# Edited"})
    assert client.get(f"/api/jobs/{job_id}").json()["pages"][0]["markdown"] == "# Edited"

    written = client.post(f"/api/jobs/{job_id}/export", json={"vault_path": vault, "strategies": ["mirror"]}).json()[
        "written"
    ]
    assert written
    assert Path(written[0]).read_text(encoding="utf-8")


def test_unknown_job_is_404(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    client = TestClient(app)
    assert client.get("/api/jobs/does-not-exist").status_code == 404


def test_scan_lists_pdfs_in_scan_folder(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    client = TestClient(app)

    # No scan folder configured yet → 400 (not a 404 or a silent empty list).
    assert client.get("/api/scan").status_code == 400

    scan_root = tmp_path / "scribe"
    (scan_root / "Math").mkdir(parents=True)
    (scan_root / "Math" / "Calculus.pdf").write_bytes(_one_page_pdf())
    (scan_root / "loose.pdf").write_bytes(_one_page_pdf())
    client.put("/api/settings", json={"scan_folder": str(scan_root)})

    pdfs = client.get("/api/scan").json()["pdfs"]
    listed = {entry["rel_path"]: entry["name"] for entry in pdfs}
    assert listed == {"Math/Calculus.pdf": "Calculus", "loose.pdf": "loose"}


def test_loose_upload_exports_under_target_dir(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    client = TestClient(app)
    vault = str(tmp_path / "vault")
    job_id = client.post("/api/jobs", files={"file": ("memo.pdf", _one_page_pdf(), "application/pdf")}).json()["job_id"]
    written = client.post(
        f"/api/jobs/{job_id}/export",
        json={"vault_path": vault, "strategies": ["mirror"], "target_dir": "inbox"},
    ).json()["written"]
    assert any("inbox" in path and path.endswith("memo.md") for path in written)


def test_export_rejects_unknown_strategy(tmp_path, monkeypatch) -> None:
    """BE-19: a typo'd strategy (free text) must 422, not silently export mirror-only."""
    monkeypatch.chdir(tmp_path)
    client = TestClient(app)
    vault = str(tmp_path / "vault")
    job_id = client.post("/api/jobs", files={"file": ("n.pdf", _one_page_pdf(), "application/pdf")}).json()["job_id"]
    response = client.post(
        f"/api/jobs/{job_id}/export",
        json={"vault_path": vault, "strategies": ["wikilnks"]},  # typo
    )
    assert response.status_code == 422


def test_corrupt_settings_json_falls_back_instead_of_500ing(tmp_path, monkeypatch) -> None:
    """BE-12: a malformed settings.json must be handled, not surfaced as an unhandled 500."""
    monkeypatch.chdir(tmp_path)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "settings.json").write_text("{not valid json", encoding="utf-8")
    client = TestClient(app)
    response = client.get("/api/settings")
    assert response.status_code == 200
    assert response.json()["strategies"] == ["mirror"]  # defaults, not a crash


def test_providers_status_reports_state(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "providers.toml").write_text(
        '[[providers]]\nid="ollama"\ndisplay_name="Ollama"\nkind="local"\nbase_url="http://127.0.0.1:1"\n\n'
        '[[providers]]\nid="gemini"\ndisplay_name="Gemini"\nkind="cloud"\nbase_url="https://x/v1"\napi_key="PUT_YOUR_KEY"\n\n'
        '[[providers]]\nid="claude"\ndisplay_name="Claude"\nkind="cloud"\ndefault_model="claude-sonnet-4-6"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr("marginalia.api.providers.is_claude_authenticated", lambda: False)
    client = TestClient(app)
    by_id = {p["id"]: p for p in client.get("/api/providers/status").json()["providers"]}
    assert by_id["ollama"]["state"] == "unreachable"  # nothing on 127.0.0.1:1
    assert by_id["gemini"]["state"] == "needs_key"  # placeholder key
    assert by_id["claude"]["state"] == "unknown"  # probe says not signed in


def test_claude_status_ready_when_authenticated(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "providers.toml").write_text(
        '[[providers]]\nid="claude"\ndisplay_name="Claude"\nkind="cloud"\ndefault_model="claude-sonnet-4-6"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr("marginalia.api.providers.is_claude_authenticated", lambda: True)
    client = TestClient(app)
    claude = client.get("/api/providers/status").json()["providers"][0]
    assert claude["state"] == "ready"  # credential detected → signed in


def test_claude_auth_detects_env_token(monkeypatch) -> None:
    from marginalia.claude_auth import is_claude_authenticated

    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "stub-token")
    assert is_claude_authenticated() is True


def test_set_cloud_key_makes_gemini_ready(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "providers.toml").write_text(
        '[[providers]]\nid="gemini"\ndisplay_name="Gemini"\nkind="cloud"\nbase_url="https://x/v1"\n',
        encoding="utf-8",
    )
    # BE-07: once a key is present the status probe actually calls the provider — stub it so the
    # test stays offline/deterministic while still exercising the "key accepted" branch.
    monkeypatch.setattr("marginalia.api.providers.runtime_status", lambda provider: (True, ["gemini-2.0-flash"]))
    client = TestClient(app)
    assert client.get("/api/providers/status").json()["providers"][0]["state"] == "needs_key"
    saved = client.post("/api/providers/gemini/key", json={"api_key": "a-real-key"}).json()
    assert saved["state"] == "ready"  # key entered in the UI, then confirmed valid by the probe
    # #148: the curated model list, not the raw probe result — the picker offers a hand-picked,
    # vision-capable set instead of whatever Gemini's own catalogue endpoint happens to return.
    assert saved["models"] == CLOUD_MODELS["gemini"]
    assert len(saved["models"]) > 1  # a real picker, not just the default model
    # persisted across requests (settings.json overlay)
    assert client.get("/api/providers/status").json()["providers"][0]["state"] == "ready"


def test_uncurated_cloud_provider_falls_back_to_probed_models(tmp_path, monkeypatch) -> None:
    """#148: a cloud provider without a curated entry still gets *some* model list (the raw probe)."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "providers.toml").write_text(
        '[[providers]]\nid="other-cloud"\ndisplay_name="Other"\nkind="cloud"\nbase_url="https://x/v1"\n'
        'api_key="a-real-key"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "marginalia.api.providers.runtime_status", lambda provider: (True, ["model-a", "model-b"])
    )
    client = TestClient(app)
    status = client.get("/api/providers/status").json()["providers"][0]
    assert status["state"] == "ready"
    assert status["models"] == ["model-a", "model-b"]


def test_gemini_bad_key_reports_invalid_key(tmp_path, monkeypatch) -> None:
    """BE-07: a *present* key that the provider rejects must not show as green/ready."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "providers.toml").write_text(
        '[[providers]]\nid="gemini"\ndisplay_name="Gemini"\nkind="cloud"\nbase_url="https://x/v1"\n'
        'api_key="a-revoked-key"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr("marginalia.api.providers.runtime_status", lambda provider: (False, []))
    client = TestClient(app)
    gemini = client.get("/api/providers/status").json()["providers"][0]
    assert gemini["state"] == "invalid_key"
    assert gemini["reachable"] is False
    assert "rejected the api key" in gemini["hint"].lower()


def test_providers_status_probes_concurrently(tmp_path, monkeypatch) -> None:
    """BE-16: N slow provider probes should take ~1 probe's time, not N * that time, to answer."""
    monkeypatch.chdir(tmp_path)
    provider_count = 4
    probe_delay = 0.2
    (tmp_path / "providers.toml").write_text(
        "\n".join(
            f'[[providers]]\nid="p{i}"\ndisplay_name="P{i}"\nkind="local"\nbase_url="http://127.0.0.1:{9000 + i}"\n'
            for i in range(provider_count)
        ),
        encoding="utf-8",
    )

    def _slow_unreachable(provider) -> tuple[bool, list[str]]:
        time.sleep(probe_delay)
        return False, []

    monkeypatch.setattr("marginalia.api.providers.runtime_status", _slow_unreachable)
    client = TestClient(app)

    start = time.perf_counter()
    response = client.get("/api/providers/status")
    elapsed = time.perf_counter() - start

    assert response.status_code == 200
    # Sequential probing would take >= provider_count * probe_delay (~0.8s); concurrent probing
    # bounds it near a single probe. Generous margin to stay robust on a loaded CI runner.
    assert elapsed < probe_delay * (provider_count - 1)


def test_set_key_rejected_for_claude(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "providers.toml").write_text(
        '[[providers]]\nid="claude"\ndisplay_name="Claude"\nkind="cloud"\n', encoding="utf-8"
    )
    client = TestClient(app)
    assert client.post("/api/providers/claude/key", json={"api_key": "x"}).status_code == 400


def test_load_on_unsupported_provider_is_501(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "providers.toml").write_text(
        '[[providers]]\nid="ollama"\ndisplay_name="Ollama"\nkind="local"\nbase_url="http://127.0.0.1:1"\n',
        encoding="utf-8",
    )
    client = TestClient(app)
    assert client.post("/api/providers/ollama/load", json={"model": "x"}).status_code == 501


def test_path_suggestion_endpoints_return_lists(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    client = TestClient(app)
    assert isinstance(client.get("/api/paths/vaults").json(), list)
    assert isinstance(client.get("/api/paths/scan-folders").json(), list)


def test_non_pdf_upload_is_400(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    client = TestClient(app)
    response = client.post("/api/jobs", files={"file": ("x.pdf", b"not a pdf", "application/pdf")})
    assert response.status_code == 400


def test_ocr_stream_with_fake_engine(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    app.dependency_overrides[get_active_engine] = lambda: _FakeEngine()
    try:
        client = TestClient(app)
        job_id = client.post("/api/jobs", files={"file": ("n.pdf", _one_page_pdf(), "application/pdf")}).json()[
            "job_id"
        ]
        body = client.get(f"/api/jobs/{job_id}/stream").text
        assert "page_started" in body
        assert "transcribed" in body
        assert "job_done" in body
    finally:
        app.dependency_overrides.clear()
