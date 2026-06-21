"""Handwriting-OCR prompts. Centralised so they can be tuned in one place.

If transcription comes out weak for some handwriting style, this is the file to touch; the rest of the
system only knows about ``handwriting_prompt()``.
"""

_HANDWRITING_PROMPT = (
    "You are an OCR engine for handwritten notes. Transcribe the handwriting in this image to "
    "clean Markdown. Preserve structure: headings, bullet and numbered lists, checkboxes "
    "(- [ ] and - [x]), and tables. Keep the original language; do not translate, summarize, or "
    "add commentary of your own. If a word is illegible, write [illegible]. "
    "Output only the Markdown, nothing else."
)


def handwriting_prompt() -> str:
    """The default prompt for transcribing one handwritten page to Markdown."""
    return _HANDWRITING_PROMPT
