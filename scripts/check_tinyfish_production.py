"""Manual hosted acceptance: creates an isolated judge trip and uses provider credit.

No cookies, tokens, keys or browser storage are saved in the report.
"""
import json
from pathlib import Path
import time

from playwright.sync_api import sync_playwright

ORIGIN = "https://voyara-travel-taupe.vercel.app"
OUT = Path(__file__).resolve().parents[1] / "report/tinyfish_production_20261019"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    report = dict(origin=ORIGIN, checks=[], page_errors=[], live_provider=True)
    started = time.monotonic()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="msedge", headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 1000})
        page = context.new_page()
        page.on("pageerror", lambda error: report["page_errors"].append(str(error)))
        page.set_default_timeout(60000)
        try:
            page.goto(ORIGIN + "/#login", wait_until="domcontentloaded")
            page.locator("#developerSignIn").filter(has_text="Continue as Judge").click()
            page.wait_for_url("**/#home")
            report["checks"].append("Hosted judge sign-in")
            page.locator(".journey-launcher").click()
            box = page.locator("#journeyMessage")
            box.wait_for(state="visible")

            def send(text):
                box.fill(text)
                began = time.monotonic()
                with page.expect_response(lambda response: response.url.endswith("/chat") and response.request.method == "POST") as pending:
                    page.locator('.journey-chat-compose button[type="submit"]').click()
                response = pending.value
                answer = response.json()
                assert response.status == 200 and answer["status"] == "ok", answer
                assert answer["mode"] == "local"
                assert answer["workspace"]["draft"]["destination"] == "Agra"
                report.setdefault("chat_seconds", []).append(round(time.monotonic()-began, 2))
                box.wait_for(state="visible")
                page.wait_for_function("!document.querySelector('#journeyMessage').disabled")
                return answer

            answer = send("i want to go for a trip to agra can you plan it")
            assert answer["awaiting"] == "start_date" and not answer["workspace"]["confirmed"]
            report["checks"].append("Exact Agra message responds locally and asks for missing details")
            answer = send("2026-12-01 for three days, two adults, INR 90000 total, relaxed, culture")
            assert not answer["workspace"]["missing_fields"]
            trip_id = answer["workspace"]["conversation_id"]
            report["trip_id"] = trip_id
            with page.expect_response(lambda response: response.url.endswith("/confirm-jobs") and response.request.method == "POST") as pending:
                page.locator('[data-chat="confirm"]').click()
            response = pending.value
            assert response.status == 202, response.text()
            job = response.json()
            report["checks"].append("Planning starts as HTTP 202 background job through Vercel")
            report["job_id"] = job["job_id"]
            research_started = time.monotonic()
            # A separate browser session must stay responsive and cannot see this trip.
            stranger = browser.new_context()
            second = stranger.request.post(ORIGIN + "/api/auth/judge", headers={"Origin": ORIGIN, "X-Voyara-Judge": "1"})
            assert second.ok, second.text()
            denied = stranger.request.get(ORIGIN + "/api/assistant/conversations/" + trip_id)
            assert denied.status == 404
            report["checks"].append("Second judge session stays responsive; private trip is inaccessible")
            stranger.close()
            deadline = time.monotonic() + 1200
            while job["status"] in {"queued", "running"}:
                assert time.monotonic() < deadline, "Planning exceeded acceptance deadline"
                time.sleep(3)
                polled = context.request.get(ORIGIN + "/api" + job["status_url"], timeout=45000)
                assert polled.ok, polled.text()
                job = polled.json()
                report["research_seconds"] = round(time.monotonic() - research_started, 2)
                (OUT / "live_browser.json").write_text(json.dumps(report, indent=2), encoding="utf8")
            assert job["status"] == "completed", job
            result = job["result"]
            orchestration = result["orchestration"]
            report["orchestration"] = orchestration
            report["agent_summary"] = [{"agent": agent["agent_id"], "status": agent["status"],
                                       "execution": agent.get("execution"), "errors": agent.get("errors", [])}
                                      for agent in orchestration.get("agent_results", [])]
            assert orchestration["status"] == "ok", report["agent_summary"]
            assert sum(agent.get("execution", {}).get("mode") == "tinyfish" and agent["execution"]["completed"]
                       for agent in orchestration["agent_results"]) == 4
            assert orchestration["trip_brief"]["destination"] == "Agra"
            assert orchestration["trip_brief"]["party_size"] == 2
            assert orchestration["itinerary"]["days"][0]["calendar_date"] == "2026-12-01"
            report["checks"].append("Four actual TinyFish roles complete with dated itinerary and calculated budget")
            page.wait_for_function("!document.querySelector('#journeyMessage').disabled", timeout=45000)
            page.screenshot(path=str(OUT / "chat.png"))
            page.locator('[data-chat="close"]').click()
            page.goto(ORIGIN + "/#travel-book/" + trip_id, wait_until="domcontentloaded")
            page.locator(".travel-plan").wait_for()
            page.reload(wait_until="domcontentloaded")
            page.locator(".travel-plan").wait_for()
            saved = context.request.get(ORIGIN + "/api/assistant/conversations/" + trip_id + "/plan").json()
            assert saved and not saved["stale"] and saved["plan"]["trip_brief"]["destination"] == "Agra"
            report["saved_plan_version"] = saved["version"]
            report["checks"].append("Travel Book and itinerary survive browser reload")
            panel = page.locator(".travel-plan .agent-work")
            panel.locator("summary").first.click()
            assert panel.get_by_text("TinyFish web research", exact=False).count() == 4
            assert panel.get_by_role("link", name="Research source").count() >= 4
            report["checks"].append("Rendered provider labels and source links")
            with page.expect_download() as pending:
                page.locator('[data-book="download"]').click()
            download = pending.value
            download.save_as(str(OUT / "Agra-Travel-Book.pdf"))
            assert (OUT / "Agra-Travel-Book.pdf").read_bytes().startswith(b"%PDF")
            report["checks"].append("Private Travel Book PDF downloads successfully")
            page.screenshot(path=str(OUT / "travel_book.png"), full_page=True)
            assert not report["page_errors"], report["page_errors"]
            report["status"] = "passed"
        except Exception as error:
            report["status"] = "failed"
            report["error"] = str(error)
            page.screenshot(path=str(OUT / "failure.png"), full_page=True)
            raise
        finally:
            report["seconds"] = round(time.monotonic() - started, 2)
            (OUT / "live_browser.json").write_text(json.dumps(report, indent=2), encoding="utf8")
            print(json.dumps({key: report.get(key) for key in ("status", "checks", "error", "seconds", "research_seconds", "page_errors")}), flush=True)
            browser.close()


if __name__ == "__main__":
    main()
