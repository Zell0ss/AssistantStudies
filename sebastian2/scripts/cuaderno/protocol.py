"""Pure logic for the cuaderno protocol: truncation, response parsing, entry formatting.
No I/O here — file reads/writes, API calls and Telegram live in despertar.py."""
import re

_TELEGRAM_RE = re.compile(r"<telegram>(.*?)</telegram>", re.DOTALL)


def truncate_notebook(text: str, max_chars: int, head_chars: int, tail_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    head = text[:head_chars]
    tail = text[-tail_chars:]
    omitted = len(text) - head_chars - tail_chars
    notice = f"\n\n[...truncado, se omitieron {omitted} caracteres del centro del cuaderno...]\n\n"
    return head + notice + tail


def parse_response(text: str) -> dict:
    match = _TELEGRAM_RE.search(text)
    return {"telegram_message": match.group(1).strip() if match else None}


def format_entry(text: str, timestamp: str) -> str:
    return f"\n\n---\n## Despertar {timestamp}\n{text}"
