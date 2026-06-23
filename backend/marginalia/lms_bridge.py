"""Headless control of LM Studio via its ``lms`` CLI (issue #44).

LM Studio exposes an OpenAI-compatible server on ``:1234``, but only once the app
(or its daemon) is running and a model is loaded. This module lets marginalia
*start the server and load a model with the GUI closed*, driven from a button —
so "all connection attempts failed" becomes "click Load" instead of a dead end.

Design (mirrors the proven ``lmcode`` bridge):
- Every public function **degrades gracefully**: returns ``False`` / ``[]`` and
  never raises when ``lms`` is absent or a subprocess fails. Callers don't catch.
- A fast ``socket`` pre-check (:func:`is_server_up`) avoids multi-second HTTP
  hangs when the server is down.
- ``lms`` ships with LM Studio but is on PATH only after ``lmstudio install-cli``;
  :func:`lms_available` is the guard for that.

--- WHERE TO CHANGE IF THINGS MOVE ---
- LM Studio's port: it is passed in (defaults to ``DEFAULT_PORT``); the catalogue
  port lives in ``providers.toml`` (``base_url``), surfaced by ``models_admin``.
- The blocking calls (:func:`ensure_server_up`, :func:`load_model`) are sync; call
  them from async routes via ``asyncio.to_thread`` so the event loop stays free.
"""

from __future__ import annotations

import json
import shutil
import socket
import subprocess
import time

DEFAULT_PORT = 1234
DEFAULT_HOST = "127.0.0.1"

# Timeouts (seconds): fast for queries, generous for VRAM loads and the cold-start "wake".
_QUERY_TIMEOUT = 5
_LIST_TIMEOUT = 30  # `lms ls/ps` can be slow while the service "wakes up" from cold
_SERVER_START_TIMEOUT = 30
_LOAD_TIMEOUT = 120
_PROBE_TIMEOUT = 0.5


def lms_available() -> bool:
    """True if the ``lms`` CLI is on PATH (does not mean the server is running)."""
    return shutil.which("lms") is not None


def is_server_up(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> bool:
    """Fast TCP probe of the LM Studio server — avoids slow HTTP timeouts when down."""
    try:
        with socket.create_connection((host, port), timeout=_PROBE_TIMEOUT):
            return True
    except OSError:
        return False


def ensure_server_up(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> bool:
    """Make the LM Studio server reachable, starting it headless if needed.

    Two-path start (the GUI may be open or fully closed):
    1. already reachable → done.
    2. ``lms server start`` — fast when the app/daemon is already running.
    3. ``lms daemon up`` — full headless daemon when nothing is running.

    Never trust the exit code alone — always re-probe the socket after each path.

    Returns True once the socket is reachable, False if it never comes up.
    """
    if is_server_up(host, port):
        return True
    if not lms_available():
        return False

    started = _run_ok(["lms", "server", "start", "--port", str(port)], timeout=_SERVER_START_TIMEOUT)
    if started and _wait_until_up(host, port, deadline=5.0):
        return True

    # GUI fully closed: bring up the headless daemon, then poll (it takes longer).
    _run_ok(["lms", "daemon", "up"], timeout=_SERVER_START_TIMEOUT)
    return _wait_until_up(host, port, deadline=30.0)


def load_model(identifier: str, gpu: str = "auto", context_length: int | None = None) -> bool:
    """Load a model into LM Studio (``lms load <id> --yes``); waits up to 120s.

    Args:
        identifier: model id as shown by ``lms ls`` / the runtime's ``/models``.
        gpu: ``"auto"`` | ``"max"`` | a ``"0.0".."1.0"`` offload fraction.
        context_length: optional context-window override.
    """
    if not lms_available():
        return False
    cmd = ["lms", "load", identifier, "--yes"]
    if gpu != "auto":
        cmd += ["--gpu", gpu]
    if context_length is not None:
        cmd += ["--context-length", str(context_length)]
    return _run_ok(cmd, timeout=_LOAD_TIMEOUT)


def unload_model(identifier: str | None = None, *, all_models: bool = False) -> bool:
    """Unload one model (``lms unload <id>``) or every model (``lms unload --all``)."""
    if not lms_available():
        return False
    if all_models:
        cmd = ["lms", "unload", "--all"]
    elif identifier:
        cmd = ["lms", "unload", identifier]
    else:
        return False
    return _run_ok(cmd, timeout=_QUERY_TIMEOUT)


def loaded_model_ids() -> list[str]:
    """Identifiers of models currently loaded in memory (``lms ps --json``)."""
    return _identifiers(_run_json(["lms", "ps", "--json"]))


def downloaded_model_ids() -> list[str]:
    """Identifiers of models present on disk (``lms ls --json``)."""
    return _identifiers(_run_json(["lms", "ls", "--json"]))


# --- helpers -----------------------------------------------------------------


def _wait_until_up(host: str, port: int, deadline: float) -> bool:
    """Poll the socket until reachable or *deadline* seconds elapse."""
    waited = 0.0
    while waited < deadline:
        if is_server_up(host, port):
            return True
        time.sleep(0.5)
        waited += 0.5
    return is_server_up(host, port)


def _identifiers(raw: object) -> list[str]:
    """Pull non-empty ``identifier``/``modelKey`` strings from an ``lms --json`` list."""
    if not isinstance(raw, list):
        return []
    ids: list[str] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        value = item.get("identifier") or item.get("modelKey") or item.get("path")
        if value:
            ids.append(str(value))
    return ids


def _run_ok(cmd: list[str], timeout: int) -> bool:
    """Run *cmd* silently; True iff it exits 0. Never raises (graceful-fail)."""
    try:
        result = subprocess.run(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout,
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, OSError):
        return False


def _run_json(cmd: list[str], timeout: int = _LIST_TIMEOUT) -> object:
    """Run *cmd*, parse stdout as JSON. None on absence/failure/invalid JSON.

    `lms` prints a ``Waking up LM Studio service...`` preamble before the JSON when the
    service is cold, so we parse from the first ``[``/``{`` rather than the whole stdout.
    """
    if not lms_available():
        return None
    try:
        result = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout)
    except (subprocess.SubprocessError, OSError):
        return None
    return _parse_json_lenient(result.stdout)


def _parse_json_lenient(text: str) -> object:
    """``json.loads`` from the first ``[``/``{``, skipping any non-JSON preamble. None on failure."""
    starts = [index for index in (text.find("["), text.find("{")) if index != -1]
    if not starts:
        return None
    try:
        return json.loads(text[min(starts) :])
    except json.JSONDecodeError:
        return None
