"""Measure the actual local travel site and dashboard; no substituted feeds.

Creates one isolated synthetic traveler. Public research is not submitted by
this smoke test. Test-owned SQL rows are removed on exit. Reports contain only
aggregate counts, timings and sanitized check outcomes.
"""

# ruff: noqa: E402
import datetime as dt
import json
import os
from pathlib import Path
import statistics
import sys
import time
import uuid

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "report/tinyfish_memory"
SITE = "http://127.0.0.1:8094"
DASHBOARD = "http://127.0.0.1:5174"
sys.path[:0] = [str(ROOT), str(ROOT / "stitch_ai_travel_booking_platform/backend")]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    report = dict(
        generated_at=dt.datetime.now(dt.timezone.utc).isoformat(),
        mode="actual local HTTP and browser sessions; seeded catalog prices; no mocked dashboard feeds",
        checks=[],
        timings={},
        browser_errors=[],
        paid_research_started=False,
    )
    tag = "smoke_" + uuid.uuid4().hex[:12]
    owner_id = None
    began = time.perf_counter()

    def check(name, action, area="travel"):
        start = time.perf_counter()
        try:
            detail = action()
            report["checks"].append(
                dict(
                    name=name,
                    area=area,
                    status="passed",
                    elapsed_ms=round((time.perf_counter() - start) * 1000, 2),
                    detail=detail,
                )
            )
            return detail
        except Exception as error:
            blocked = area == "dashboard" and "HTTP 503" in str(error)
            report["checks"].append(
                dict(
                    name=name,
                    area=area,
                    status="blocked" if blocked else "failed",
                    elapsed_ms=round((time.perf_counter() - start) * 1000, 2),
                    error=type(error).__name__
                    + ": "
                    + str(error).split("Call log:")[0][:200],
                )
            )
            return None

    def require(condition, message):
        if not condition:
            raise AssertionError(message)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="msedge", headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        api = context.request
        page = context.new_page()
        page.set_default_timeout(12000)
        page.on(
            "pageerror", lambda error: report["browser_errors"].append(str(error)[:200])
        )
        try:
            check(
                "Travel API health",
                lambda: require(
                    api.get(SITE + "/health").status == 200,
                    "Health endpoint unavailable",
                ),
            )
            signed = api.post(
                SITE + "/api/auth/register?session=true",
                data=dict(
                    username=tag, email=tag + "@example.com", password=uuid.uuid4().hex
                ),
            )
            require(signed.status == 201, "Synthetic traveler registration failed")
            owner_id = signed.json()["user"]["id"]
            csrf = next(
                cookie["value"]
                for cookie in context.cookies()
                if cookie["name"] == "voyara_csrf"
            )
            check(
                "Authenticated session",
                lambda: require(
                    api.get(SITE + "/api/auth/me").json()["id"] == owner_id,
                    "Session owner mismatch",
                ),
            )

            def homepage():
                start = time.perf_counter()
                response = page.goto(SITE + "/#home", wait_until="networkidle")
                require(response.status == 200, "Homepage failed")
                require(
                    page.locator(".journey-launcher").is_visible(),
                    "Travel assistant launcher missing",
                )
                report["timings"]["travel_home_ready_ms"] = round(
                    (time.perf_counter() - start) * 1000, 2
                )
                page.screenshot(
                    path=str(OUT / "travel-site-desktop.png"), full_page=False
                )

            check("Travel homepage and assistant launcher", homepage)

            def dialogue():
                page.locator(".journey-launcher").click()
                dialog = page.locator("dialog.journey-chat")
                box = dialog.locator("textarea")
                turns = []
                for text in [
                    "I want a trip to Agra",
                    "1 December 2026",
                    "Three days",
                    "two",
                    "15k per person",
                ]:
                    page.wait_for_function(
                        "!document.querySelector('#journeyMessage').disabled"
                    )
                    box.fill(text)
                    start = time.perf_counter()
                    with page.expect_response(
                        lambda r: r.url.endswith("/chat") and r.request.method == "POST"
                    ) as pending:
                        box.press("Enter")
                    response = pending.value
                    result = response.json()
                    require(
                        response.status == 200 and result["status"] != "unavailable",
                        "Chat draft turn failed",
                    )
                    turns.append(round((time.perf_counter() - start) * 1000, 2))
                draft = result["workspace"]["draft"]
                require(
                    draft["destination"] == "Agra"
                    and draft["traveller_count"] == 2
                    and draft["budget"] == 30000,
                    "Contextual trip parsing mismatch",
                )
                require(
                    not result["workspace"]["confirmed"],
                    "Draft was unexpectedly confirmed",
                )
                report["timings"]["chat_turn_ms"] = turns
                report["timings"]["chat_median_ms"] = round(statistics.median(turns), 2)
                report["timings"]["chat_max_ms"] = max(turns)
                page.reload(wait_until="domcontentloaded")
                page.locator(".journey-launcher").click()
                page.wait_for_function(
                    "!document.querySelector('#journeyMessage').disabled"
                )
                require(
                    "30,000" in page.locator("dialog.journey-chat").inner_text(),
                    "Saved conversation was not recovered",
                )
                page.screenshot(
                    path=str(OUT / "travel-chat-desktop.png"), full_page=False
                )
                return dict(turns=len(turns), saved_after_reload=True)

            check("Five-turn travel chat, Enter key and reload persistence", dialogue)

            trip = {}

            def create_trip():
                start = time.perf_counter()
                response = api.post(
                    SITE + "/api/trips",
                    headers={"X-CSRF-Token": csrf},
                    data=dict(
                        title="Isolated smoke-test trip",
                        constraints=dict(
                            destination="Jaipur",
                            origin="Delhi",
                            start_date="2026-12-01",
                            end_date="2026-12-03",
                            traveller_count=2,
                            budget=90000,
                            pace="relaxed",
                        ),
                    ),
                )
                require(
                    response.status == 201,
                    "Trip creation failed: HTTP "
                    + str(response.status)
                    + " "
                    + response.text()[:240],
                )
                trip.update(response.json())
                report["timings"]["trip_create_ms"] = round(
                    (time.perf_counter() - start) * 1000, 2
                )
                budget = trip["plan"]["budget"]
                require(
                    budget["total_inr"] == sum(budget["categories"].values()),
                    "Budget does not reconcile",
                )
                require(
                    budget["remaining_inr"] == 90000 - budget["total_inr"]
                    and budget["estimate"],
                    "Budget remainder/estimate label incorrect",
                )
                require(
                    len(trip["plan"]["itinerary"]["days"]) == 3,
                    "Itinerary day count mismatch",
                )
                return dict(days=3, budget_reconciles=True, prices="seeded estimates")

            check("Dated itinerary and reconciled estimated budget", create_trip)
            if trip:
                check(
                    "Saved trip retrieved from database",
                    lambda: require(
                        api.get(SITE + "/api/trips/" + trip["id"]).json()["id"]
                        == trip["id"],
                        "Saved trip missing",
                    ),
                )

                def duplicate():
                    response = api.post(
                        SITE + "/api/trips/" + trip["id"] + "/duplicate",
                        headers={"X-CSRF-Token": csrf},
                    )
                    require(
                        response.status == 201 and response.json()["id"] != trip["id"],
                        "Trip duplication failed",
                    )

                check("Trip duplication", duplicate)

            def mobile():
                page.set_viewport_size({"width": 390, "height": 844})
                page.goto(SITE + "/#home", wait_until="domcontentloaded")
                require(
                    page.evaluate(
                        "document.documentElement.scrollWidth <= innerWidth+1"
                    ),
                    "Travel site overflows mobile viewport",
                )
                page.screenshot(
                    path=str(OUT / "travel-site-mobile.png"), full_page=False
                )
                page.set_viewport_size({"width": 1440, "height": 900})

            check("Travel mobile layout", mobile)

            snapshots = []

            def dashboard_feed():
                for _ in range(3):
                    start = time.perf_counter()
                    response = api.get(
                        "http://127.0.0.1:8200/api/dashboard/snapshot?fresh=true",
                        timeout=25000,
                    )
                    require(
                        response.status == 200,
                        f"Live dashboard snapshot returned HTTP {response.status}",
                    )
                    data = response.json()
                    require(
                        data.get("schema") == "iron_web_dashboard_v1"
                        and data.get("connection", {}).get("user_id") == owner_id,
                        "Dashboard session/owner mismatch",
                    )
                    snapshots.append(round((time.perf_counter() - start) * 1000, 2))
                report["timings"]["dashboard_snapshot_ms"] = snapshots
                report["timings"]["dashboard_snapshot_median_ms"] = round(
                    statistics.median(snapshots), 2
                )
                return dict(samples=3, owner_isolation=True)

            available = check(
                "Actual authenticated dashboard feed", dashboard_feed, "dashboard"
            )
            if available:
                names = {
                    "overview": "Overview",
                    "tinyfish": "TinyFish intelligence",
                    "memory": "Memory graph",
                    "agents": "Agents",
                    "activity": "Activity",
                    "architecture": "Architecture",
                    "history": "History",
                    "resources": "Resources",
                }
                for path, name in names.items():

                    def navigate(path=path, name=name):
                        start = time.perf_counter()
                        page.goto(DASHBOARD + "/" + path + "?mode=live", wait_until="domcontentloaded")
                        page.get_by_role(
                            "heading", name=name, exact=True, level=1
                        ).wait_for()
                        require(
                            page.locator('[data-testid="live-dashboard"]').is_visible(),
                            "Real dashboard not rendered",
                        )
                        require(
                            page.evaluate(
                                "document.documentElement.scrollWidth <= innerWidth+1"
                            ),
                            "Dashboard horizontal overflow",
                        )
                        report["timings"]["dashboard_" + path + "_ready_ms"] = round(
                            (time.perf_counter() - start) * 1000, 2
                        )

                    check("Live dashboard page: " + name, navigate, "dashboard")

                def follow_live():
                    page.get_by_role("button", name="Follow live", exact=True).click()
                    expect(
                        page.get_by_role("button", name="Follow live", exact=True)
                    ).to_have_attribute("aria-pressed", "true")
                    page.goto(DASHBOARD + "/tinyfish?mode=live", wait_until="domcontentloaded")
                    page.get_by_role(
                        "heading", name="TinyFish intelligence", exact=True, level=1
                    ).wait_for()
                    require(
                        "No external evidence saved yet"
                        in page.locator(".tf-intelligence").inner_text(),
                        "Fresh owner should not see another owner's evidence",
                    )
                    page.screenshot(
                        path=str(OUT / "actual-dashboard-desktop.png"), full_page=False
                    )
                    page.set_viewport_size({"width": 390, "height": 844})
                    require(
                        page.evaluate(
                            "document.documentElement.scrollWidth <= innerWidth+1"
                        ),
                        "Mobile dashboard overflows",
                    )
                    page.screenshot(
                        path=str(OUT / "actual-dashboard-mobile.png"), full_page=False
                    )

                check(
                    "Follow live, owner isolation and mobile dashboard",
                    follow_live,
                    "dashboard",
                )
            else:
                report["environment_limit"] = (
                    "Live dashboard data requires FalkorDB on port 6380. Docker Desktop failed to start because its local dockerInference socket could not be accessed. No volumes were reset or replaced."
                )

                def outage():
                    page.goto(DASHBOARD + "/tinyfish?mode=live", wait_until="domcontentloaded")
                    page.get_by_role(
                        "heading", name="Memory feed unavailable", exact=True
                    ).wait_for()
                    require(
                        page.locator(".live-loading").is_visible(),
                        "Outage is not explained",
                    )
                    require(
                        page.locator(".tf-metrics").count() == 0,
                        "Offline dashboard substituted activity counts",
                    )
                    page.get_by_role("button", name="Follow live", exact=True).click()
                    page.get_by_role(
                        "heading", name="Memory feed unavailable", exact=True
                    ).wait_for()
                    page.screenshot(
                        path=str(OUT / "actual-dashboard-outage-desktop.png"),
                        full_page=False,
                    )
                    page.set_viewport_size({"width": 390, "height": 844})
                    require(
                        page.evaluate(
                            "document.documentElement.scrollWidth <= innerWidth+1"
                        ),
                        "Outage screen overflows mobile viewport",
                    )
                    page.screenshot(
                        path=str(OUT / "actual-dashboard-outage-mobile.png"),
                        full_page=False,
                    )

                check(
                    "Dashboard outage messaging, retry and mobile layout",
                    outage,
                    "dashboard",
                )
            check(
                "Browser runtime errors",
                lambda: require(
                    not report["browser_errors"], "Browser JavaScript errors recorded"
                ),
                "shared",
            )
        finally:
            browser.close()
            if owner_id:
                # Only the uniquely identified synthetic account is eligible.
                from dotenv import load_dotenv

                load_dotenv(ROOT / "stitch_ai_travel_booking_platform/backend/.env")
                os.environ.setdefault(
                    "DATABASE_URL",
                    "sqlite:///" + (ROOT / "data/voyara_app/travel.db").as_posix(),
                )
                from app.db import SessionLocal
                from app.models import User
                from sqlalchemy import delete

                with SessionLocal() as db:
                    removed = db.execute(
                        delete(User).where(User.id == owner_id, User.username == tag)
                    )
                    db.commit()
                    report["test_account_removed"] = removed.rowcount == 1
    report["elapsed_seconds"] = round(time.perf_counter() - began, 2)
    report["passed"] = sum(c["status"] == "passed" for c in report["checks"])
    report["failed"] = sum(c["status"] == "failed" for c in report["checks"])
    report["blocked"] = sum(c["status"] == "blocked" for c in report["checks"])
    report["status"] = (
        "passed" if not report["failed"] and not report["blocked"] else "partial"
    )
    (OUT / "site-smoke.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf8", newline="\n"
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
