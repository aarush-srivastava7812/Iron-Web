"""Headless rendering and checks of the exported graph (no desktop input)."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

directory = Path(__file__).resolve().parent
url = json.loads((directory/"server.json").read_text())["url"]
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(channel="msedge", headless=True)
    page = browser.new_page(viewport={"width": 1500, "height": 1050}, device_scale_factor=1)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(url, wait_until="networkidle")
    assert page.locator(".node").count() == 13
    assert page.locator(".edge").count() == 13
    page.locator(".node").first.click()
    assert '"kind": "Entity"' in page.locator("#detail").inner_text()
    page.locator("#obs").uncheck()
    assert page.locator(".node").count() == 5
    assert page.locator(".edge").count() == 5
    page.screenshot(path=str(directory/"entities.png"), full_page=True)
    page.locator("#obs").check()
    page.locator("#reset").click()
    page.screenshot(path=str(directory/"full_graph.png"), full_page=True)
    page.locator("#mode").select_option("default")
    assert page.locator(".node").count() == 3
    assert page.locator(".edge").count() == 0
    page.screenshot(path=str(directory/"default_graph.png"), full_page=True)
    assert not errors, errors
    browser.close()
(directory/"viewer_verified.json").write_text(json.dumps({"entity_nodes": 5, "observation_nodes": 8,
    "edges": 13, "default_observations": 3, "default_edges": 0, "node_inspection": True,
    "observation_toggle": True, "browser_errors": errors}, indent=2))
print("Graph viewer verified: 13 nodes, 13 edges; entity projection 5/5; default run 3/0; node details; no browser errors.")
