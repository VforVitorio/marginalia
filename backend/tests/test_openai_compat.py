"""``parse_sse_delta`` parsing + the chat-completions payload shape."""

from marginalia.ocr.openai_compat import OpenAICompatEngine, parse_sse_delta


def test_parses_content_delta() -> None:
    line = 'data: {"choices":[{"delta":{"content":"Hello"}}]}'
    assert parse_sse_delta(line) == "Hello"


def test_ignores_done_and_keepalive() -> None:
    assert parse_sse_delta("data: [DONE]") is None
    assert parse_sse_delta(": keep-alive") is None
    assert parse_sse_delta("") is None


def test_ignores_delta_without_content() -> None:
    line = 'data: {"choices":[{"delta":{"role":"assistant"}}]}'
    assert parse_sse_delta(line) is None


def test_ignores_malformed_json() -> None:
    assert parse_sse_delta("data: {not json}") is None


def test_payload_includes_system_prompt_and_image() -> None:
    engine = OpenAICompatEngine(id="x", display_name="X", kind="local", base_url="http://h/v1", model="m")
    payload = engine._build_payload(b"PNGDATA", "go")
    assert payload["messages"][0]["role"] == "system"
    user_content = payload["messages"][1]["content"]
    types = {block["type"] for block in user_content}
    assert {"text", "image_url"} <= types
