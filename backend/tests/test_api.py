"""API flow: settings, create-from-upload, fetch, page image, edit, export, and the OCR stream."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pymupdf
from fastapi.testclient import TestClient

from marginalia.api.deps import get_active_engine
from marginalia.api.main import app
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
    client = TestClient(app)
    assert client.get("/api/providers/status").json()["providers"][0]["state"] == "needs_key"
    saved = client.post("/api/providers/gemini/key", json={"api_key": "a-real-key"}).json()
    assert saved["state"] == "ready"  # key entered in the UI flips it to ready
    # persisted across requests (settings.json overlay)
    assert client.get("/api/providers/status").json()["providers"][0]["state"] == "ready"


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
