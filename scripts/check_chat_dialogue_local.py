"""Local chatbot UI acceptance. Never confirms a trip or starts paid research."""
import json
from pathlib import Path
import time
import uuid
from urllib.error import URLError
from urllib.request import urlopen

from playwright.sync_api import sync_playwright


def main():
    origin = "http://127.0.0.1:8094"
    out = Path(__file__).resolve().parents[1] / "report/chat_dialogue_20261019"
    out.mkdir(parents=True, exist_ok=True)
    report = {"checks": [], "turns": [], "page_errors": [], "paid_research_started": False}
    deadline = time.monotonic()+60
    while time.monotonic() < deadline:
        try:
            if urlopen(origin+"/health", timeout=2).status == 200:
                break
        except (URLError, TimeoutError):
            pass
        time.sleep(0.5)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="msedge", headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 1000})
        page = context.new_page()
        page.set_default_timeout(30000)
        page.on("pageerror", lambda error: report["page_errors"].append(str(error)))
        tag = "chat_ui_"+uuid.uuid4().hex[:10]
        signed = context.request.post(origin+"/api/auth/register?session=true", data={
            "username": tag, "email": tag+"@example.com", "password": uuid.uuid4().hex})
        assert signed.status == 201
        try:
            page.goto(origin+"/#home", wait_until="domcontentloaded")
            page.locator(".journey-launcher").click()
            dialog = page.locator("dialog.journey-chat")
            box = dialog.locator("textarea")
            page.wait_for_function("!document.querySelector('#journeyMessage').disabled")

            def send(text, chip=False):
                began = time.monotonic()
                if not chip:
                    box.fill(text)
                with page.expect_response(lambda response: response.url.endswith("/chat") and response.request.method == "POST") as pending:
                    if chip:
                        dialog.locator(".journey-chat-actions").get_by_role("button", name=text, exact=True).click()
                    else:
                        dialog.locator('[type="submit"]').click()
                response = pending.value
                assert response.status == 200, response.text()
                result = response.json()
                assert result["status"] != "unavailable", result
                page.wait_for_function("!document.querySelector('#journeyMessage').disabled")
                assert not box.input_value(), "Saved turns should leave room for the next answer"
                report["turns"].append({"input": text, "reply": result["reply"], "awaiting": result.get("awaiting"),
                                        "seconds": round(time.monotonic()-began, 3)})
                return result

            first = send("I want a trip to Agra")
            assert first["awaiting"] == "start_date" and first["reply"].count("?") == 1
            send("1 December 2026")
            third = send("Three days", chip=True)
            trip_id = third["workspace"]["conversation_id"]
            page.reload(wait_until="domcontentloaded")
            page.locator(".journey-launcher").click()
            page.wait_for_function("!document.querySelector('#journeyMessage').disabled")
            count = send("two")
            assert count["workspace"]["draft"]["traveller_count"] == 2
            budget = send("15k per person")
            assert budget["workspace"]["draft"]["budget"] == 30000
            assert not budget["workspace"]["confirmed"] and not budget["workspace"]["plan_ready"]
            report["checks"].append("Contextual questions, quick replies, short answers after reload, and transparent group-budget arithmetic")
            information=send("Tell me about Agra")
            assert "Taj Mahal" in information["reply"] and "https://agra.nic.in/tourist-places/" in information["reply"]
            assert information["workspace"]["draft"] == budget["workspace"]["draft"]
            report["checks"].append("Destination information is sourced and read-only")
            preview = send("Show hotels in Jaipur")
            assert preview["workspace"]["draft"]["destination"] == "Agra"
            assert preview["cards"] and all(card["preview_only"] for card in preview["cards"])
            assert dialog.locator(".journey-chat-cards [data-choice-kind]").count() == 0
            report["checks"].append("Read-only destination previews cannot select a hotel for the wrong trip")
            corrected = send("Jaipur instead of Agra")
            assert corrected["workspace"]["draft"]["destination"] == "Jaipur"
            updated = send("Increase my budget by 5k")
            assert updated["workspace"]["draft"]["budget"] == 35000
            summary = send("Show my budget")
            assert "35,000" in summary["reply"] and "spending limit" in summary["reply"]
            assert summary["workspace"]["revision"] == updated["workspace"]["revision"]
            ambiguous = send("Maybe Agra or Jaipur")
            assert ambiguous["status"] == "needs_clarification"
            assert ambiguous["workspace"]["draft"] == updated["workspace"]["draft"]
            report["checks"].append("Corrections preserve other facts; summaries and ambiguous choices preserve the draft")
            page.wait_for_function("(() => {const el=document.querySelector('.journey-chat-scroll');return el.scrollTop+el.clientHeight>=el.scrollHeight-2;})()")
            dialog.screenshot(path=str(out/"conversation.png"))

            # UI-only simulated provider failure, separate from the real dialogue above.
            workspace_url = origin+"/api/assistant/conversations/"+trip_id+"/workspace"
            work = context.request.get(workspace_url).json()
            fake_url = "/assistant/conversations/"+trip_id+"/planning-jobs/simulated-ui-failure"
            work["research"] = {"job_id": "simulated-ui-failure", "status": "failed", "status_url": fake_url,
                                "failed_specialists": [{"name": "Restaurant research", "reason": "Research timed out"}]}
            page.route("**/workspace", lambda route: route.fulfill(json=work))
            page.route("**/planning-jobs/simulated-ui-failure", lambda route: route.fulfill(json={"status": "failed"}))
            page.reload(wait_until="domcontentloaded")
            page.locator(".journey-launcher").click()
            notice = dialog.locator(".journey-research-notice")
            notice.filter(has_text="Restaurant research").wait_for()
            notice.get_by_role("button", name="Check progress").click()
            dialog.locator(".journey-chat-status").filter(has_text="Research could not finish").wait_for()
            assert "provider credit" in notice.inner_text()
            report["checks"].append("Simulated provider failure explains the failed specialist, preserves details, and offers progress checking without a new run")
            dialog.screenshot(path=str(out/"simulated_failure_recovery.png"))
            page.unroute("**/workspace")
            page.unroute("**/planning-jobs/simulated-ui-failure")
            held = []
            page.route("**/assistant/conversations/*/chat", lambda route: held.append(route))
            box.fill("Show my trip summary")
            dialog.locator('[type="submit"]').click()
            dialog.locator(".journey-chat-status").filter(has_text="The chat took too long").wait_for(timeout=26000)
            assert box.is_enabled() and box.input_value() == "Show my trip summary"
            assert dialog.locator(".journey-chat-loading").is_hidden()
            for route in held:
                route.abort()
            report["checks"].append("Stalled network request restores controls and retains unsent input")
            assert not report["page_errors"], report["page_errors"]
            report["status"] = "passed"
        except Exception as error:
            report["status"], report["error"] = "failed", str(error)
            page.screenshot(path=str(out/"failure.png"), full_page=True)
            raise
        finally:
            (out/"browser.json").write_text(json.dumps(report, indent=2), encoding="utf8")
            print(json.dumps({key: report.get(key) for key in ("status", "checks", "page_errors", "error")}), flush=True)
            browser.close()


if __name__ == "__main__":
    main()
