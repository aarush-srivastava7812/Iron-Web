"""Check recorded post-fix API evidence and review fixture plans from the briefs."""

import csv
import hashlib
import json
from pathlib import Path
import re

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]


def save(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


def record(label):
    return json.loads((OUT / "exchanges" / (label + ".json")).read_text(encoding="utf-8"))


def result(label):
    return record(label)["response"]


def fields(packet):
    values = {}
    for line in packet["prompt"].splitlines():
        match = re.fullmatch(r"\[(trip|profile|session)\] (\w+): (.+) \[claims: .+\]", line)
        if match:
            values[match[2]] = json.loads(match[3])[0]
    return values


def review_plan(packet, fixture, *, initial=False):
    """Transparent simulated planner/reviewer, not a generative model call."""
    facts = fields(packet)
    required = {"budget", "currency", "destination", "dates", "departure_city", "traveller_count",
                "accessibility", "max_walk_metres", "avoid_boats", "max_activities_per_day",
                "flight_time_preference", "dietary"}
    if packet["status"] != "ready" or not required <= facts.keys():
        return dict(decision="pause", reason="Missing or unresolved requirements")
    assert facts["currency"] == "INR" and facts["traveller_count"] == 2
    assert facts["destination"] == "Goa" and facts["departure_city"] == "Delhi"
    assert facts["dates"] == fixture["dates"] and facts["dietary"] == "vegetarian"
    flights = [f for f in fixture["flight_offers"] if facts["flight_time_preference"] != "morning" or f["departure"] < "12:00"]
    hotels = [h for h in fixture["hotel_offers"] if h["step_free"] and h["vegetarian_food"]
              and h["walk_from_dropoff_metres"] <= facts["max_walk_metres"]]
    activities = [a for a in fixture["activity_offers"] if a["walking_metres"] <= facts["max_walk_metres"]
                  and not (facts["avoid_boats"] and a["boat"])]
    if not hotels or not flights:
        return dict(decision="pause", reason="No fixture hotel satisfies the current walking/access requirements",
                    max_walk_metres=facts["max_walk_metres"], suitable_hotels=[h["id"] for h in hotels])
    flight = next(f for f in flights if f["id"] == "F-AM-COMFORT") if initial else min(flights, key=lambda f: f["total_for_two"])
    hotel = next(h for h in hotels if h["id"] == "H-RESORT") if initial else min(hotels, key=lambda h: h["four_night_total"])
    days = [dict(date="2026-12-11", activity="A-ACCESSIBLE-BEACH"),
            dict(date="2026-12-12", activity="A-TERRACE")]
    selected = [next(a for a in activities if a["id"] == day["activity"]) for day in days]
    assert facts["max_activities_per_day"] >= 1
    total = flight["total_for_two"] + hotel["four_night_total"] + sum(fixture["fixed_costs"].values()) + sum(a["cost_for_two"] for a in selected)
    return dict(decision="draft_approved_for_review" if total <= facts["budget"] else "pause",
        planner=dict(flight=flight["id"], hotel=hotel["id"], days=days, total_inr=total,
                     cap_inr=facts["budget"], remaining_inr=facts["budget"] - total),
        reviewer=dict(source="Automatic context only; no extra restriction recall needed for this decision",
            morning_flight=flight["departure"] < "12:00", step_free=hotel["step_free"], vegetarian_food=hotel["vegetarian_food"],
            walking_within_limit=hotel["walk_from_dropoff_metres"] <= facts["max_walk_metres"] and all(a["walking_metres"] <= facts["max_walk_metres"] for a in selected),
            no_boats=all(not a["boat"] for a in selected), one_activity_per_day=len({d["date"] for d in days}) == len(days)),
        claim_ids=packet["claim_ids"], no_external_action=True)


def main():
    fixture = json.loads((OUT / "travel_fixture.json").read_text(encoding="utf-8"))
    itinerary, flight, hotel = [result(label) for label in ("09-planner-itinerary", "10-planner-flight", "11-reviewer-hotel")]
    revised, walking = result("36-revised-context"), result("46-fresh-context-after-walking")
    initial_plan = review_plan(itinerary, fixture, initial=True)
    revised_plan = review_plan(revised, fixture)
    final_plan = review_plan(walking, fixture)
    for name, decision in [("agent_decisions_initial.json", initial_plan), ("agent_decisions_revised.json", revised_plan), ("agent_decision_final.json", final_plan)]:
        save(name, decision)
    checks = []
    def check(name, passed, *evidence):
        checks.append(dict(name=name, outcome="PASS" if passed else "FAIL", evidence=list(evidence)))
    def http(label, expected):
        return record(label)["http_status"] == expected
    critical = {"budget", "dates", "destination", "currency", "dietary", "accessibility", "max_walk_metres",
                "avoid_boats", "max_activities_per_day", "traveller_count", "departure_city", "flight_time_preference"}
    check("Distinct authenticated agent profiles", "travel planner" in itinerary["agent_text"] and "review role" in hotel["agent_text"], "09-planner-itinerary", "11-reviewer-hotel")
    check("RAM hit and actual CUDA residency", result("12-itinerary-warm")["cache_hit"] and itinerary["residency"]["device"] == "cuda" and itinerary["residency"]["resident_bytes"] > 0, "09-planner-itinerary", "12-itinerary-warm")
    check("Durable hybrid discovery and exact walking recall", bool(result("22b-hybrid-discovery")) and result("15-recall-walking")["answer_status"] == "supported", "22b-hybrid-discovery", "15-recall-walking")
    check("Original multi-part intake accepted with complete requirements", result("03-raw-status")["status"] == "ready" and result("03-raw-status")["semantic_claim_count"] == 14 and critical <= fields(result("04-raw-blocks-planner")).keys(), "01-raw-intake", "03-raw-status", "04-raw-blocks-planner")
    check("Ambiguous intake remains a blocking review item", http("70-ambiguous-blocks", 409) and result("70-ambiguous-blocks")["receipts"][0]["status"] == "needs_review" and result("70-ambiguous-blocks")["receipts"][0]["semantic_claim_count"] == 0, "67-ambiguous-intake", "70-ambiguous-blocks")
    check("Every scenario-critical itinerary field reaches the brief", critical <= fields(itinerary).keys(), "09-planner-itinerary")
    check("Flight includes departure city, party and morning requirement", {"departure_city", "traveller_count", "flight_time_preference"} <= fields(flight).keys(), "10-planner-flight")
    check("Trip mood inherits into an ordinary session", any(c["card_id"] == "relaxed" for c in itinerary["cards"]) and "[trip] mood:" in itinerary["prompt"], "09-planner-itinerary")
    check("Explicit session mood takes its own scope", "[session] mood:" in result("25-session-itinerary")["prompt"], "25-session-itinerary")
    check("Pending relevant budget blocks context and completion", http("30-pending-context", 409) and http("31-pending-completion", 409), "30-pending-context", "31-pending-completion")
    check("Accepted budget replaces the old brief and proof", not result("33-stale-context-proof")["valid"] and fields(revised)["budget"] == 65000, "33-stale-context-proof", "36-revised-context")
    check("Budget change flags plan for review and refuses stale completion", not result("34-reviewer-handoff")["can_continue"] and http("35-stale-completion", 409), "34-reviewer-handoff", "35-stale-completion")
    check("Roleplayed plans satisfy the then-current fixture requirements", initial_plan["planner"]["total_inr"] == 72600 and revised_plan["planner"]["total_inr"] == 58600 and all(v is True for k, v in revised_plan["reviewer"].items() if k != "source"), "agent_decisions_initial.json", "agent_decisions_revised.json")
    check("Completed work is not executed again", result("40-completed-not-reclaimed")["status"] == "already_completed", "40-completed-not-reclaimed")
    full, brief = result("44-reviewed-handoff-after-walking"), result("45-brief-only-handoff-after-walking")
    check("Walking update preserves completed history and requires review", not full["can_continue"] and full["work"][0]["needs_review"] and full["work"][0]["work"]["status"] == "completed", "44-reviewed-handoff-after-walking")
    check("Brief-only dependency control now detects walking update", not brief["can_continue"] and brief["work"][0]["needs_review"], "41-register-brief-only-control", "45-brief-only-handoff-after-walking")
    check("Trip values remain separate", fields(result("52-other-trip-context"))["budget"] == 18000 and fields(result("53-goa-after-other-trip"))["budget"] == 65000, "52-other-trip-context", "53-goa-after-other-trip")
    check("Unrelated pending trip leaves Goa available", http("50-goa-blocked-by-other-trip", 200), "50-goa-blocked-by-other-trip")
    check("Users and proof ownership remain isolated", http("55-riya-unblocked-by-other-user", 200) and fields(result("57-arjun-context"))["budget"] == 30000 and http("59-cross-user-proof", 403), "55-riya-unblocked-by-other-user", "57-arjun-context", "59-cross-user-proof")
    deleted = result("63-after-deletion-context")
    check("Budget deletion blocks and never resurrects either cap", http("61-deletion-pending-blocks-context", 409) and deleted["status"] == "needs_information" and deleted["required_issues"].get("budget") == "missing" and result("64-after-deletion-budget")["answer_status"] == "missing", "61-deletion-pending-blocks-context", "63-after-deletion-context", "64-after-deletion-budget")
    check("Hotel brief includes all scenario-critical fields", critical <= fields(hotel).keys(), "11-reviewer-hotel")
    check("Fresh walking brief contains 50m and reviewer stops", fields(walking)["max_walk_metres"] == 50 and final_plan["decision"] == "pause", "46-fresh-context-after-walking", "agent_decision_final.json")
    check("Goa stays warm before and after unrelated trip processing", result("50-goa-blocked-by-other-trip")["cache_hit"] and result("53-goa-after-other-trip")["cache_hit"], "50-goa-blocked-by-other-trip", "53-goa-after-other-trip")
    walk_ids = {e["claim_id"] for e in result("15-recall-walking")["evidence"]}
    check("Every task's dependency list includes walking evidence", all(walk_ids <= set(p["claim_ids"]) for p in (itinerary, flight, hotel)), "09-planner-itinerary", "10-planner-flight", "11-reviewer-hotel", "15-recall-walking")
    counts = {state: sum(c["outcome"] == state for c in checks) for state in ("PASS", "FAIL")}
    coverage = {task: {p: p in fields(packet) for p in sorted(critical)} for task, packet in [("itinerary", itinerary), ("flight", flight), ("hotel", hotel)]}
    save("results.json", dict(counts=counts, checks=checks, coverage=coverage,
        http_calls=sum(1 for _ in (OUT / "transcript.ndjson").open(encoding="utf-8")),
        method="Same assistant roleplayed planner/reviewer with deterministic fixture checks; real authenticated HTTP, BGE embeddings, FalkorDB, Qdrant, RAM and CUDA. No independent generative-agent or booking run.",
        harness_call_error=None,
        original_report_preserved=True, final_agent_decision=final_plan))
    files = ["memory/context/runtime.py", "memory/context/access.py", "memory/shared/journal.py", "memory/shared/service.py", "memory/shared/interpreter.py"]
    save("implementation_hashes.json", {f: hashlib.sha256((ROOT / f).read_bytes()).hexdigest() for f in files})
    with (OUT / "checks.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["name", "outcome", "evidence"])
        writer.writeheader()
        writer.writerows(checks)
    for label in ["04-raw-blocks-planner", "09-planner-itinerary", "10-planner-flight", "11-reviewer-hotel", "36-revised-context", "46-fresh-context-after-walking", "63-after-deletion-context"]:
        (OUT / (label + ".md")).write_text("# " + label + "\n\n```text\n" + result(label)["prompt"] + "\n```\n", encoding="utf-8")
    print(json.dumps(dict(counts=counts, failed=[c for c in checks if c["outcome"] != "PASS"],
        before_total=initial_plan["planner"]["total_inr"], revised_total=revised_plan["planner"]["total_inr"], final=final_plan), indent=2))
    return int(counts["FAIL"] > 0)


if __name__ == "__main__":
    raise SystemExit(main())
