"""Manual local browser acceptance; uses real TinyFish research and memory."""
import json
from pathlib import Path
import time
from urllib.error import URLError
from urllib.request import urlopen

from playwright.sync_api import sync_playwright


def main():
    origin = "http://127.0.0.1:8094"
    root = Path(__file__).resolve().parents[1]
    out = root / "report" / "tinyfish_local_20261019"
    out.mkdir(parents=True, exist_ok=True)
    report = {"origin": origin, "provider": "TinyFish", "live_provider": True, "checks": [], "page_errors": []}
    started = time.monotonic()
    deadline = started + 60
    while True:
        try:
            with urlopen(origin + "/health", timeout=2) as ready:
                if ready.status == 200:
                    break
        except (URLError, TimeoutError):
            pass
        if time.monotonic() >= deadline:
            raise RuntimeError("Local test server did not become ready on port 8094")
        time.sleep(0.5)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="msedge", headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 1000})
        page = context.new_page()
        page.set_default_timeout(30000)
        page.on("pageerror", lambda error: report["page_errors"].append(str(error)))
        try:
            page.goto(origin + "/#login", wait_until="domcontentloaded")
            page.locator("#developerSignIn").click()
            page.wait_for_url("**/#home")
            report["checks"].append("Local demo sign-in")
            page.goto(origin + "/#planner", wait_until="domcontentloaded")
            form = page.locator("#plannerForm")
            form.locator('[name="place"]').select_option(label="Jaipur")
            form.locator('[name="date"]').fill("2026-12-01")
            form.locator('[name="duration"]').select_option("3")
            form.locator('[name="group"]').select_option("2")
            form.locator('[name="budget"]').fill("90000")
            form.locator('[name="interests"][value="Culture"]').check()
            form.locator('[name="interests"][value="Food"]').check()
            with page.expect_response(lambda r: r.url.endswith("/message-jobs") and r.request.method == "POST", timeout=600000) as pending:
                form.locator('[type="submit"]').click()
            response = pending.value
            report["http_status"] = response.status
            job = response.json()
            assert response.status == 202
            while job["status"] in {"queued", "running"}:
                time.sleep(2)
                job = context.request.get(origin + "/api" + job["status_url"]).json()
            assert job["status"] == "completed", job
            result = job["result"]
            report["planner_response"] = result
            orchestration = result.get("orchestration", {})
            report["seconds"] = round(time.monotonic() - started, 2)
            report["agent_summary"] = [{"agent": a["agent_id"], "status": a["status"],
                "execution": a.get("execution"), "errors": a.get("errors", [])}
                for a in orchestration.get("agent_results", [])]
            print(json.dumps({"seconds": report["seconds"], "http_status": response.status,
                              "status": orchestration.get("status"), "agents": report["agent_summary"]}), flush=True)
            assert response.status == 202, "Planner job request failed"
            assert orchestration.get("status") == "ok", "Research/validation did not complete"
            assert result["connection_status"] == "agents_connected"
            assert sum(a.get("execution", {}).get("mode") == "tinyfish" and a["execution"]["completed"] for a in orchestration["agent_results"]) == 4
            assert orchestration["trip_brief"]["budget_total_inr"] == 90000
            assert orchestration["trip_brief"]["party_size"] == 2
            assert orchestration["itinerary"]["days"][0]["calendar_date"] == "2026-12-01"
            page.locator("#savePlanStatus").filter(has_text="Itinerary saved to My Trips.").wait_for(timeout=30000)
            report["checks"].append("Real provider research, dated plan, budget calculation and saved draft")
            panel = page.locator(".travel-plan .agent-work")
            panel.locator("summary").first.click()
            assert panel.get_by_text("TinyFish web research", exact=False).count() == 4
            assert panel.get_by_role("link", name="Research source").count() >= 4
            report["checks"].append("Visible TinyFish labels and source links")
            trip_id = job["status_url"].split("/")[3]
            plan_url = origin + "/api/assistant/conversations/" + trip_id + "/plan"
            saved = context.request.get(plan_url).json()
            assert saved["version"] >= 1 and not saved["stale"]
            report["checks"].append("Authenticated persisted draft can be read back")
            page.screenshot(path=str(out / "planner.png"), full_page=True)
            assert report["page_errors"] == [], report["page_errors"]
            report["status"] = "passed"
        except Exception as error:
            report["status"] = "failed"
            report["error"] = str(error)
            page.screenshot(path=str(out / "failure.png"), full_page=True)
            raise
        finally:
            report["seconds"] = round(time.monotonic() - started, 2)
            (out / "live_browser.json").write_text(json.dumps(report, indent=2), encoding="utf8")
            browser.close()


if __name__ == "__main__":
    main()
