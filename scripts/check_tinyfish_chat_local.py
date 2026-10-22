"""Reproduce the reported Agra chat issue against the local application."""
import json
from pathlib import Path
import time
from urllib.error import URLError
from urllib.request import urlopen

from playwright.sync_api import sync_playwright


def main():
    origin = "http://127.0.0.1:8094"
    out = Path(__file__).resolve().parents[1] / "report" / "tinyfish_chat_fix_20261019"
    out.mkdir(parents=True, exist_ok=True)
    report = {"checks": [], "page_errors": []}
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        try:
            with urlopen(origin + "/health", timeout=2) as response:
                if response.status == 200:
                    break
        except (URLError, TimeoutError):
            pass
        time.sleep(0.5)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.set_default_timeout(30000)
        page.on("pageerror", lambda error: report["page_errors"].append(str(error)))
        try:
            page.goto(origin + "/#login", wait_until="domcontentloaded")
            page.locator("#developerSignIn").click()
            page.wait_for_url("**/#home")
            page.locator(".journey-launcher").click()
            dialog = page.locator("dialog.journey-chat")
            field = dialog.locator("textarea")
            field.wait_for(state="visible")
            field.fill("i want to go for a trip to agra can you plan it")
            started = time.monotonic()
            with page.expect_response(lambda r: r.url.endswith("/chat") and r.request.method == "POST") as pending:
                dialog.locator('[type="submit"]').click()
            response = pending.value
            data = response.json()
            elapsed = time.monotonic() - started
            assert response.status == 200 and data["status"] == "ok", data
            assert data["workspace"]["draft"]["destination"] == "Agra"
            assert "departure date" in data["reply"] and data["awaiting"] == "start_date"
            assert elapsed < 10, elapsed
            page.wait_for_function("!document.querySelector('.journey-chat textarea').disabled")
            assert dialog.locator(".journey-chat-loading").is_hidden()
            assert "NVIDIA-powered" not in dialog.inner_text()
            report["response_seconds"] = round(elapsed, 3)
            report["reply"] = data["reply"]
            report["checks"].append("Exact Agra message returns missing-detail questions and clears loading")
            dialog.screenshot(path=str(out / "agra_reply.png"))
            field.fill("2026-12-01 for three days, two adults, INR 30000 total")
            with page.expect_response(lambda r: r.url.endswith("/chat") and r.request.method == "POST") as pending:
                dialog.locator('[type="submit"]').click()
            result = pending.value.json()
            assert not result["workspace"]["missing_fields"]
            assert result["workspace"]["draft"]["end_date"] == "2026-12-03"
            page.wait_for_function("!document.querySelector('.journey-chat textarea').disabled")
            report["checks"].append("Follow-up saves exact dates, duration, party and budget for review")
            held = []
            page.route("**/assistant/conversations/*/chat", lambda route: held.append(route))
            field.fill("Show me stays for my trip")
            dialog.locator('[type="submit"]').click()
            dialog.locator(".journey-chat-status").filter(has_text="The chat took too long").wait_for(timeout=26000)
            assert field.is_enabled() and field.input_value() == "Show me stays for my trip"
            assert dialog.locator(".journey-chat-loading").is_hidden()
            assert dialog.locator('[type="submit"]').is_enabled()
            for route in held:
                try:
                    route.abort()
                except Exception:
                    pass
            page.unroute("**/assistant/conversations/*/chat")
            report["checks"].append("Stalled request times out, preserves input and restores controls")
            assert not report["page_errors"], report["page_errors"]
            report["status"] = "passed"
            print(json.dumps(report), flush=True)
        except Exception as error:
            report["status"], report["error"] = "failed", str(error)
            page.screenshot(path=str(out / "failure.png"), full_page=True)
            raise
        finally:
            (out / "browser.json").write_text(json.dumps(report, indent=2), encoding="utf8")
            browser.close()


if __name__ == "__main__":
    main()
