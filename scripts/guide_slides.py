"""Render offline slides with shared, keyboard-accessible controls."""

from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent
IDS = ["intro", "system", "memory", "tinyfish", "vector-memory", "graph-memory",
       "evidence", "tools", "workflow", "impact", "results", "verification",
       "locomo", "dmr", "longmemeval", "latency", "protocol", "conclusion"]


def render_slides(contents, titles, details):
    if len(contents) != len(IDS) or len(titles) != len(IDS):
        raise ValueError("Slide contents, titles and identifiers must match")
    document = (ROOT / "tinyfish_slide_template.html").read_text(encoding="utf-8")
    values = {
        "OPTIONS": "".join(
            f'<option value="{identifier}">{i+1}. {escape(title)}</option>'
            for i, (identifier, title) in enumerate(zip(IDS, titles))
        ),
        "SLIDES": "".join(
            f'<section class="slide" id="{identifier}" role="group" aria-roledescription="slide" aria-label="{i+1} of {len(IDS)}: {escape(title)}"'
            + ("" if i == 0 else " hidden")
            + f'><div class="slide-content">{content}</div></section>'
            for i, (identifier, title, content) in enumerate(zip(IDS, titles, contents))
        ),
        "DETAILS": details,
        "COUNT": str(len(IDS)),
        "PRESENTATION_STYLE": (ROOT / "presentation_layout.css").read_text(encoding="utf-8"),
        "ARCHITECTURE_STYLE": (ROOT / "memory_architecture_slides.css").read_text(encoding="utf-8"),
        "SCRIPT": (ROOT / "slide_controls.js").read_text(encoding="utf-8"),
    }
    for key, value in values.items():
        document = document.replace("{{" + key + "}}", value)
    return document
