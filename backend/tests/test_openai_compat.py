"""``parse_sse_delta`` extracts the text from chat-completions SSE lines."""

from marginalia.ocr.openai_compat import parse_sse_delta


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
