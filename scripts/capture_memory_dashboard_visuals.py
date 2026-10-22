"""Capture the dashboard's labelled architecture illustrations for the offline deck."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "report/tinyfish_memory/dashboard-visuals"
URL = "http://127.0.0.1:5174/architecture?mode=history"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page(viewport={"width": 1600, "height": 1100}, reduced_motion="reduce")
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(URL)
        gallery = page.get_by_label("Vector, graph and hybrid memory illustrations")
        gallery.wait_for()
        page.evaluate("document.fonts.ready")
        for name in ("vector", "graph", "hybrid"):
            card = page.locator(f'[data-memory-visual="{name}"]')
            assert "Architecture illustration" in card.locator("footer").inner_text()
            card.locator("svg").screenshot(path=str(OUT / f"{name}.jpg"), type="jpeg", quality=90)
        assert not errors, errors
        browser.close()
    (OUT / "sources.json").write_text(json.dumps({
        "source": URL,
        "mode": "saved project replay",
        "kind": "Architecture illustrations, not measured embeddings or live records",
        "captures": [f"{name}.jpg" for name in ("vector", "graph", "hybrid")],
        "browser_errors": errors,
    }, indent=2) + "\n", encoding="utf-8")
    print("Captured vector, graph and hybrid SVG panels from the dashboard.")


if __name__ == "__main__":
    main()
