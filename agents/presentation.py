"""Traveler-facing findings derived from validated results, never execution traces."""
import ipaddress
import re
from urllib.parse import urlsplit

from agents.schemas import AgentPresentation, TravelerFinding


TITLES = {
    "trip_consultant": "Your trip preferences",
    "explore_agent": "Destination ideas",
    "stay_agent": "Where to stay",
    "tour_guide_agent": "Things to do",
    "food_guide_agent": "Where to eat",
    "itinerary_planner": "Your day-by-day plan",
    "budget_booking_agent": "Your trip budget",
    "travel_support_agent": "Before you travel",
    "travel_orchestrator": "Your travel plan",
}


def public_text(value, limit=600):
    """Reject reasoning/debug payloads accidentally placed in display fields."""
    text = str(value or "").strip()
    if re.search(r"<\s*/?\s*(?:think|analysis|reasoning)\b|\[/?(?:analysis|reasoning)\]|"
                 r"(?:API[_ -]?KEY|Bearer\s+|Traceback|system prompt|tool_calls|"
                 r"source_quote|retention_base|CUDAExecutionProvider)", text, re.I):
        return ""
    return text[:limit].rstrip()


def source_url(evidence):
    if evidence is None or evidence.source != "tinyfish.web":
        return None
    try:
        parsed = urlsplit(evidence.ref or "")
        host = parsed.hostname or ""
        if parsed.scheme != "https" or not host or parsed.username or parsed.password:
            return None
        if host == "localhost" or host.endswith((".localhost", ".local")):
            return None
        try:
            if not ipaddress.ip_address(host).is_global:
                return None
        except ValueError:
            pass
        return evidence.ref
    except ValueError:
        return None


def money(value):
    return "Price to confirm" if value is None else f"₹{value:,}"


def research_failure(reason):
    """Keep an actionable failure category without echoing provider diagnostics."""
    if re.search(r"timed?\s*out|timeout", str(reason or ""), re.I):
        return "Research timed out before this part could be checked."
    return "Could not finish checking this part of your trip."


def present_agent(result):
    title = TITLES.get(result.agent_id, "Your travel team")
    view = AgentPresentation(title=title, status="ready", overview="")
    if result.status in {"failed", "skipped", "needs_clarification"}:
        view.status = "unavailable" if result.status == "failed" else "needs_review"
        view.overview = "This part of your trip still needs attention. Your saved preferences are unchanged."
        view.notes = ["Review the trip details and try this part again before relying on a complete plan."]
        return view

    def finding(name, detail="", price=None, evidence=None):
        clean_name = public_text(name, 180)
        if clean_name:
            view.findings.append(TravelerFinding(
                title=clean_name, detail=public_text(detail), price=price,
                source_url=source_url(evidence)))

    # A planner may carry its selected options too; show those in their own role.
    if result.agent_id == "stay_agent":
        for option in result.stay_options[:3]:
            detail = "; ".join(filter(None, [option.location, *option.pros[:2]]))
            if option.amenities:
                detail += ". Amenities listed: " + ", ".join(option.amenities[:4])
            finding(option.name, detail,
                    money(option.price_per_night_inr) + " per room / night" if option.price_per_night_inr is not None else "Nightly rate to confirm",
                    option.evidence)
        view.overview = "These stays are options to compare for your trip. Check room occupancy, cancellation terms and availability before choosing."
    elif result.agent_id == "food_guide_agent":
        for option in result.food_options[:3]:
            finding(option.name, "; ".join(filter(None, [option.location, option.cuisine, option.dietary_fit])),
                    money(option.approx_price_per_guest_inr) + " per guest / meal" if option.approx_price_per_guest_inr is not None else "Meal price to confirm",
                    option.evidence)
        view.overview = "Use these food options to plan meal breaks. Confirm your dietary and allergy requirements directly with the venue."
    elif result.agent_id == "tour_guide_agent":
        for option in result.attractions[:3]:
            detail = "; ".join(filter(None, [option.location, option.why_fit]))
            if option.approx_duration_min:
                detail += f". Allow about {option.approx_duration_min} minutes."
            finding(option.name, detail,
                    money(option.price_per_person_inr) + " per guest" if option.price_per_person_inr is not None else "Admission price to confirm",
                    option.evidence)
        view.overview = "These experiences give you places to build the day around. Check opening times and allow for travel between stops."
    elif result.agent_id == "explore_agent":
        for option in result.destination_ideas[:3]:
            finding(option.name, "; ".join(filter(None, [option.region, option.why_fit, option.seasonality_note])), evidence=option.evidence)
        view.overview = "Here are destination findings to help you choose what to explore. Use the sources to check current visiting details."
    elif result.agent_id == "itinerary_planner" and result.itinerary:
        days = result.itinerary.days
        view.overview = f"Your {len(days)}-day outline includes time for visits, meals and breaks. The schedule is provisional until travel times and opening hours are checked."
        for day in days[:7]:
            details = "; ".join(f"{s.start_time}{'–' + s.end_time if s.end_time else ''}: {public_text(s.title, 150)}"
                                for s in day.stops if public_text(s.title, 150))
            finding(f"Day {day.day}" + (f" · {day.calendar_date}" if day.calendar_date else ""), details or "Keep this day open for arrival, departure or rest.")
        if len(days) > 7:
            view.notes.append("The remaining days are in your full itinerary.")
    elif result.agent_id == "budget_booking_agent" and result.budget:
        budget = result.budget
        unit = "per person" if budget.per_person else "for the group"
        view.overview = (f"The indicative estimate is {money(budget.total_inr)} {unit}."
                         if budget.costs_complete else
                         f"Known-cost subtotal: {money(budget.total_inr)} {unit}. The full trip total is still unknown."
                         if budget.total_inr else "The trip total is awaiting supplier quotes.")
        for line in budget.lines:
            finding(line.category.replace("_", " ").capitalize(), public_text(line.note), money(line.amount_inr))
        if not budget.costs_complete:
            categories = [public_text(c.replace("_", " "), 80) for c in budget.unknown_categories]
            view.notes.append("Still to price: " + ", ".join(filter(None, categories)) + "." if any(categories)
                              else "Some costs are unknown. The subtotal does not establish that the trip fits your budget.")
        view.notes.append("Prices are indicative; confirm the final inclusions and supplier quotes before booking.")
    elif result.agent_id == "trip_consultant" and result.trip_brief:
        brief = result.trip_brief
        view.overview = "The plan uses the trip details you supplied."
        for label, value in [("Destination", brief.destination), ("Pace", brief.pace),
                             ("Interests", ", ".join(brief.interests)),
                             ("Dietary requirements", ", ".join(brief.dietary_requirements)),
                             ("Accessibility needs", ", ".join(brief.accessibility_needs))]:
            if value:
                finding(label, value)
    elif result.guidance:
        view.overview = "Review these practical preparations before you travel."
        finding(result.guidance.topic, result.guidance.guidance)
        view.notes.extend(filter(None, (public_text(c) for c in result.guidance.risks[:3])))

    research_role = result.agent_id in {"explore_agent", "stay_agent", "food_guide_agent", "tour_guide_agent"}
    view.sources = list(dict.fromkeys(url for e in result.evidence if (url := source_url(e))))[:3]
    if research_role and not view.findings:
        view.status = "needs_review"
        view.overview = ("We found useful source pages, but there is not enough checked detail to recommend a specific option yet."
                         if view.sources else "No suitable option could be checked for this part of your trip yet.")
        view.notes.append("Review the available sources or choose another option before finalizing this part.")
    if research_role and view.findings:
        web = any(e.source == "tinyfish.web" for e in result.evidence)
        view.notes.append("Web research by TinyFish; prices, availability and suitability still need confirmation."
                          if web else "Catalog suggestions with indicative prices; confirm current details with the supplier.")
    if not view.overview:
        view.status = "needs_review"
        view.overview = "This part of the trip needs more detail before it can be recommended."
    return view


def travel_response(state):
    """Compose a useful overview from structured evidence, without another model call."""
    results = state.get("agent_results", [])
    brief = state.get("trip_brief")
    itinerary, budget = state.get("itinerary"), state.get("budget")
    for result in results:
        result.presentation = present_agent(result)
    destination = public_text(brief.destination, 180) if brief and brief.destination else "your trip"
    intro = f"Here is your travel draft for {destination}."
    details = []
    if brief:
        if brief.start_date and brief.end_date:
            details.append(f"{brief.start_date:%d %b %Y} to {brief.end_date:%d %b %Y}")
        if brief.party_size:
            details.append(f"{brief.party_size} traveler{'s' if brief.party_size != 1 else ''}")
        if brief.pace:
            details.append(f"{brief.pace} pace")
        if brief.budget_total_inr is not None:
            details.append(f"spending limit {money(brief.budget_total_inr)} for the group")
    parts = [intro + ("\n" + " · ".join(details) if details else "")]
    seen = set()
    for result in results:
        if result.agent_id in seen or result.agent_id in {"trip_consultant", "itinerary_planner", "budget_booking_agent", "travel_orchestrator"}:
            continue
        seen.add(result.agent_id)
        view = result.presentation
        lines = [view.title, view.overview]
        for item in view.findings:
            lines.append("• " + item.title + (" — " + item.detail if item.detail else "") + (" · " + item.price if item.price else ""))
        parts.append("\n".join(lines))
    if itinerary:
        days = []
        for day in itinerary.days[:10]:
            stops = [f"{s.start_time}: {public_text(s.title, 160)}" for s in day.stops if public_text(s.title, 160)]
            days.append(f"Day {day.day}: " + "; ".join(stops or ["Keep open for arrival, departure or rest."]))
        parts.append("Your day-by-day outline\n" + "\n".join(days))
        if len(itinerary.days) > 10:
            parts.append("Open the full itinerary to review the remaining days.")
    if budget:
        from agents.schemas import AgentResult
        view = present_agent(AgentResult(agent_id="budget_booking_agent", status="ok", budget=budget))
        parts.append("Your budget\n" + view.overview + "\n" + "\n".join(
            f"• {item.title}: {item.price}" for item in view.findings) + "\n" + " ".join(view.notes))
    checks = [public_text(issue.message) for issue in state.get("validation_issues", [])
              if issue.severity in {"warning", "error"}]
    if brief:
        checks.extend(public_text(c) for c in brief.hard_constraints)
    if itinerary:
        checks.extend(public_text(c) for c in itinerary.unresolved_conflicts)
    if budget:
        checks.extend(public_text(c) for c in budget.warnings)
    checks = list(dict.fromkeys(filter(None, checks)))
    if checks:
        parts.append("Before you finalize\n" + "\n".join("• " + c for c in checks))
    if any(r.status == "failed" for r in results):
        parts.append("Some parts are incomplete. Review the sections that need attention before using this as a complete plan.")
    parts.append("Next, review your stay and daily activities in the trip details. Confirm supplier prices, availability and any mandatory requirements before booking.")
    return "\n\n".join(parts)
