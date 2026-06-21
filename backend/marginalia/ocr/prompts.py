"""Prompts de OCR de manuscrito. Centralizados para afinarlos en un solo sitio.

Si la transcripción sale floja para cierto estilo de letra, este es el archivo a tocar; el resto
del sistema solo conoce ``handwriting_prompt()``.
"""

_HANDWRITING_PROMPT = (
    "You are an OCR engine for handwritten notes. Transcribe the handwriting in this image to "
    "clean Markdown. Preserve structure: headings, bullet and numbered lists, checkboxes "
    "(- [ ] and - [x]), and tables. Keep the original language; do not translate, summarize, or "
    "add commentary of your own. If a word is illegible, write [illegible]. "
    "Output only the Markdown, nothing else."
)


def handwriting_prompt() -> str:
    """El prompt por defecto para transcribir una página manuscrita a Markdown."""
    return _HANDWRITING_PROMPT
