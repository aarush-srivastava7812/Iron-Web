"""Render the isolated fixture dashboard in a fresh headless Edge context."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

root = next(parent for parent in Path(__file__).resolve().parents if (parent/"server.py").exists() and (parent/"memory").is_dir())
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(channel="msedge", headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 1000})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto("http://127.0.0.1:18765/", wait_until="networkidle")
    page.locator("#status").wait_for()
    page.locator("#query").fill("Python memory")
    page.locator("#searchForm button").click()
    page.locator(".result-card").wait_for()
    assert page.locator(".result-card p").first.inner_text().startswith("<script>")
    assert page.evaluate("typeof window.unexpected") == "undefined"
    assert page.locator("#reportStatus").inner_text() == "No verified evaluation results are available."
    page.locator("#content").fill("Browser verification sample")
    page.locator("#addForm button").click()
    page.wait_for_function("document.querySelector('#addStatus').textContent.startsWith('Saved as')")
    page.screenshot(path=str(root/"report/verification/dashboard_verification.png"), full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    assert errors == [], errors
    (root/"report/verification/dashboard_verification.json").write_text(json.dumps(dict(
        fixture_only=True, desktop_and_mobile=True, literal_text_safe=True, save_and_search=True,
        no_fabricated_results=True, browser_errors=errors), indent=2), encoding="utf-8")
    browser.close()
print("Browser verification passed: desktop, mobile, save/search, literal text and empty results.")
