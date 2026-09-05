import html
import re


def strip_html_to_text(raw_html: str) -> str:
    text = re.sub(r"<ix:header.*?</ix:header>", " ", raw_html, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()
