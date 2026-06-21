"""Format a stream of event dicts as Server-Sent Events.

Native SSE framing (docs/ARCHITECTURE.md §4): one ``data: <json>`` line per event. Shared by the jobs
OCR stream and the model-pull stream.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator


async def sse_stream(events: AsyncIterator[dict]) -> AsyncIterator[str]:
    """Wrap each event dict as an SSE ``data:`` frame."""
    async for event in events:
        yield f"data: {json.dumps(event)}\n\n"
