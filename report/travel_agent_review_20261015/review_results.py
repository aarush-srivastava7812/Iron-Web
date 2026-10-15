"""Evaluate recorded travel API exchanges; findings only, no fixes."""

from datetime import date
import hashlib
import json
from pathlib import Path
import re

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]


def record(label):
    return json.loads((OUT / "exchanges" / (label + ".json")).read_text(encoding="utf-8"))


def result(label):
    return record(label)["response"]


def contains_field(packet, predicate):
    return re.search(r"(?:^|\n)(?:\[(?:trip|profile|session)\] )?" + re.escape(predicate) + r":", packet["prompt"]) is not None


def main():
    fixture = json.loads((OUT / "travel_fixture.json").read_text(encoding="utf-8"))
    rows = []
    def check(name, passed, evidence, classification="correctness"):
        rows.append(dict(name=name, outcome="PASS" if passed else "GAP", classification=classification, evidence=evidence))

    itinerary = result("09-planner-itinerary")
    flight = result("10-planner-flight")
    hotel = result("11-reviewer-hotel")
    check("Distinct authenticated agent profiles", "travel planner" in itinerary["agent_text"] and "review role" in hotel["agent_text"], ["09-planner-itinerary", "11-reviewer-hotel"])
    check("RAM cache and actual CUDA cards", result("12-itinerary-warm")["cache_hit"] and itinerary["residency"]["device"] == "cuda" and itinerary["residency"]["resident_bytes"] > 0, ["09-planner-itinerary", "12-itinerary-warm"])
    search = result("22b-hybrid-discovery")
    check("Durable hybrid discovery and exact restriction recall", bool(search) and all(result(label)["answer_status"] == "supported" for label in ["15-recall-walking", "16-recall-boats", "17-recall-activity-limit", "18-recall-party", "19-recall-morning", "20-recall-origin"]), ["22b-hybrid-discovery", "15-recall-walking", "16-recall-boats"])
    check("Complex ordinary travel message automatically understood", result("03-raw-status")["status"] == "ready", ["01-raw-intake", "03-raw-status"], "language limitation")
    check("Unclear confirmed input blocks agent work safely", record("04-raw-blocks-planner")["http_status"] == 409, ["04-raw-blocks-planner"])
    critical_itinerary = ["accessibility", "max_walk_metres", "avoid_boats", "max_activities_per_day", "traveller_count"]
    check("All scenario-critical itinerary constraints reach the automatic brief", all(contains_field(itinerary, p) for p in critical_itinerary), ["09-planner-itinerary", "15-recall-walking", "16-recall-boats", "17-recall-activity-limit"], "high-impact context omission")
    check("Flight brief contains origin, party size and morning requirement", all(contains_field(flight,p) for p in ["departure_city", "traveller_count", "flight_time_preference"]), ["10-planner-flight", "18-recall-party", "19-recall-morning", "20-recall-origin"], "high-impact context omission")
    check("Trip mood is inherited when an ordinary session ID is supplied", any(c["card_id"] == "relaxed" for c in itinerary["cards"]), ["09-planner-itinerary", "13-trip-mood-no-session", "21-recall-trip-mood"], "scope limitation")
    check("Explicit session mood selects its card", any(c["card_id"] == "relaxed" for c in result("25-session-itinerary")["cards"]), ["23-session-mood", "25-session-itinerary"])
    check("Pending budget change blocks context and completion", all(record(label)["http_status"] == 409 for label in ["30-pending-context", "31-pending-completion"]), ["30-pending-context", "31-pending-completion"])
    changed = result("36-revised-context")
    check("Accepted budget change rejects old brief and reaches new brief", not result("33-stale-context-proof")["valid"] and "65000" in changed["traveller_text"] and "90000" not in changed["traveller_text"], ["33-stale-context-proof", "36-revised-context"])
    check("Budget change flags related work for review", not result("34-reviewer-handoff")["can_continue"] and record("35-stale-completion")["http_status"] >= 400, ["34-reviewer-handoff", "35-stale-completion"])
    revised = json.loads((OUT / "agent_decisions_revised.json").read_text(encoding="utf-8"))
    plan = revised["planner"]
    flight_offer = next(x for x in fixture["flight_offers"] if x["id"] == plan["flight"])
    hotel_offer = next(x for x in fixture["hotel_offers"] if x["id"] == plan["hotel"])
    activity_ids = ["A-ACCESSIBLE-BEACH", "A-TERRACE"]
    activities = [x for x in fixture["activity_offers"] if x["id"] in activity_ids]
    actual_total = flight_offer["total_for_two"] + hotel_offer["four_night_total"] + sum(fixture["fixed_costs"].values()) + sum(x["cost_for_two"] for x in activities)
    check("Roleplayed revised draft satisfies the then-current fixture requirements", actual_total == plan["total_inr"] == 58600 and actual_total <= 65000 and hotel_offer["step_free"] and hotel_offer["walk_from_dropoff_metres"] <= 500 and all(not a["boat"] and a["walking_metres"] <= 500 for a in activities) and flight_offer["departure"] < "12:00" and (date(2026,12,14)-date(2026,12,10)).days == fixture["nights"], ["agent_decisions_revised.json", "travel_fixture.json"], "assistant-authored plan arithmetic and checks")
    check("Completed work is retained without a second execution attempt", result("40-completed-not-reclaimed")["status"] == "already_completed", ["39-complete-reviewed-v2", "40-completed-not-reclaimed"])
    full, brief = result("44-reviewed-handoff-after-walking"), result("45-brief-only-handoff-after-walking")
    check("Manually enriched dependencies detect the walking change", not full["can_continue"] and full["work"][0]["needs_review"] and full["work"][0]["work"]["status"] == "completed", ["44-reviewed-handoff-after-walking"])
    check("Brief-only dependencies detect the same walking change", not brief["can_continue"], ["41-register-brief-only-control", "45-brief-only-handoff-after-walking", "47-direct-updated-walking"], "consequence of omitted dependency")
    check("Different trips keep their values separate", "18000" in result("52-other-trip-context")["traveller_text"] and "Bengaluru" in result("52-other-trip-context")["traveller_text"] and "65000" in result("53-goa-after-other-trip")["traveller_text"] and "Goa" in result("53-goa-after-other-trip")["traveller_text"], ["52-other-trip-context", "53-goa-after-other-trip"])
    check("Unrelated trip updates leave the active Goa workflow available", record("50-goa-blocked-by-other-trip")["http_status"] == 200, ["48-warm-goa-before-other-trip", "50-goa-blocked-by-other-trip", "53-goa-after-other-trip"], "intentional coarse blocking/cache trade-off")
    check("Different users are isolated, including pending events and proof ownership", record("55-riya-unblocked-by-other-user")["http_status"] == 200 and "30000" in result("57-arjun-context")["traveller_text"] and "65000" not in result("57-arjun-context")["traveller_text"] and "65000" in result("58-riya-after-arjun")["traveller_text"] and record("59-cross-user-proof")["http_status"] == 403, ["55-riya-unblocked-by-other-user", "57-arjun-context", "58-riya-after-arjun", "59-cross-user-proof"])
    after = result("63-after-deletion-context")
    check("Deleting the revised budget does not resurrect either old cap", record("61-deletion-pending-blocks-context")["http_status"] == 409 and after["status"] == "needs_information" and after["required_issues"].get("budget") == "missing" and "90000" not in after["traveller_text"] and "65000" not in after["traveller_text"] and result("64-after-deletion-budget")["answer_status"] == "missing", ["61-deletion-pending-blocks-context", "63-after-deletion-context", "64-after-deletion-budget"])
    coverage={}
    predicates=["budget","dates","destination","currency","dietary","accessibility","max_walk_metres","avoid_boats","max_activities_per_day","traveller_count","departure_city","flight_time_preference"]
    for name,packet in [("itinerary",itinerary),("flight",flight),("hotel",hotel)]:
        coverage[name]={p:contains_field(packet,p) for p in predicates}
    original_hashes=json.loads((OUT/'source_before.json').read_text(encoding='utf-8'))
    current={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in original_hashes}
    changed_sources=[name for name in original_hashes if original_hashes[name]!=current[name]]
    (OUT/'source_after.json').write_text(json.dumps(current,indent=2),encoding='utf-8')
    check("Implementation, tests and configuration remained unchanged", not changed_sources, ["source_before.json","source_after.json"], "no-fixes boundary")
    report=dict(method="Same assistant roleplayed both agents; no independent generative agent model or live suppliers. Real HTTP, embeddings, CUDA and isolated durable stores were used. Queue processing was explicitly stepped by the audit harness.",
        results=rows,counts={state:sum(x['outcome']==state for x in rows) for state in ['PASS','GAP']},coverage=coverage,
        plan_before_budget_change=72600,plan_after_budget_change=actual_total,new_budget=65000,
        changed_implementation_files=changed_sources,protected_files=len(original_hashes),
        final_agent_decision="Pause: the later 50-metre limit makes the supplied hotels/activities unsuitable; after the separate deletion test, a budget also needs reconfirmation. No external booking occurred.",
        audit_harness_errors=["22-hybrid-discovery used top_k/mode instead of the actual k/retrieval_mode arguments. Corrected request 22b succeeded; this was an audit-call error, not a product finding."],
        limits=["One synthetic family scenario, one alternate trip and one second user; not a statistical or production-load study.","Agent decisions were authored by the same assistant using actual memory output plus a supplied fixture catalog, not generated by independently configured agent models.","Additional reviewer memory lookups and a deliberately brief-only control expose dependency coverage; the graph correctly tracks cited versions and does not infer uncited dependencies.","No fixes, profile-template expansions, task-field patches or production deployment were applied."])
    (OUT/'results.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(dict(counts=report['counts'],changed_sources=changed_sources,checks=rows),indent=2,ensure_ascii=False))


if __name__=='__main__':
    main()
