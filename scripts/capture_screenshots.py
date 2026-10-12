"""
Automated screenshot capture script for Iron Web Research Dashboard.
Tests every aspect of the dashboard live via Playwright and saves high-resolution screenshots.
"""
import os
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
SCREENSHOT_DIR = ROOT / "screenshots"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


def capture_all_aspects():
    url = "http://127.0.0.1:8080/"
    print(f"Connecting to live dashboard at {url}...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        # 1. Load Dashboard
        page.goto(url, wait_until="networkidle")
        time.sleep(2)  # wait for telemetry fetch

        print("Capturing 01: Dashboard Overview & GPU Telemetry...")
        page.screenshot(path=str(SCREENSHOT_DIR / "01_dashboard_overview_telemetry.png"), full_page=True)

        # 2. Live Search Execution
        print("Testing Live Search Execution...")
        search_btn = page.locator("#searchSubmitBtn")
        search_btn.click()
        
        # Wait for search results container to have cards
        page.wait_for_selector(".result-card", timeout=15000)
        time.sleep(1)
        print("Capturing 02: Live IRL Search Results...")
        page.screenshot(path=str(SCREENSHOT_DIR / "02_live_irl_search_results.png"), full_page=True)

        # 3. Live Memory Ingestion
        print("Testing Live Memory Ingestion...")
        page.locator("#ingestContentInput").fill("Deep Learning models run on NVIDIA RTX 4050 with INT8 quantization.")
        page.locator("#ingestEntitiesInput").fill("deep_learning, rtx_4050, cuda")
        page.locator("#ingestSubmitBtn").click()
        time.sleep(2)
        print("Capturing 03: Live Memory Ingestion...")
        page.screenshot(path=str(SCREENSHOT_DIR / "03_live_memory_ingestion.png"), full_page=True)

        # 4. Official Benchmarks Tab
        print("Switching to Official Benchmarks Tab...")
        page.locator('button[data-tab="benchmarks"]').click()
        time.sleep(1)
        print("Capturing 04: Official Benchmarks...")
        page.screenshot(path=str(SCREENSHOT_DIR / "04_official_benchmarks.png"), full_page=True)

        # 5. Ablations Tab
        print("Switching to Ablations & Baselines Tab...")
        page.locator('button[data-tab="ablations"]').click()
        time.sleep(1)
        print("Capturing 05: Component Ablations...")
        page.screenshot(path=str(SCREENSHOT_DIR / "05_component_ablations.png"), full_page=True)

        # 6. Competitor Comparison Tab
        print("Switching to vs Mem0 / Zep / MemPalace Tab...")
        page.locator('button[data-tab="competitors"]').click()
        time.sleep(1)
        print("Capturing 06: Competitor Comparison...")
        page.screenshot(path=str(SCREENSHOT_DIR / "06_competitor_comparison.png"), full_page=True)

        # 7. MCP & API Tab
        print("Switching to MCP & Engine API Tab...")
        page.locator('button[data-tab="mcp"]').click()
        time.sleep(1)
        print("Capturing 07: MCP & Engine API...")
        page.screenshot(path=str(SCREENSHOT_DIR / "07_mcp_api_tools.png"), full_page=True)

        browser.close()
        print(f"\nAll aspects captured successfully! Screenshots saved in {SCREENSHOT_DIR}")


if __name__ == "__main__":
    capture_all_aspects()
