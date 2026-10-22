"""Local dialogue policy: interpret, validate, acknowledge, ask one question.

Drafts and dialogue state remain private working state. Chat never starts paid
research or promotes unconfirmed facts to the traveler's durable memory.
"""
from copy import deepcopy
import re

from fastapi import HTTPException
from pydantic import ValidationError

from .conversation_intake import ALIASES, PUBLIC_PLACES, understand

_UNSET = object()

QUESTIONS = {
    "destination": "Where would you like to go?",
    "start_date": "What is your departure date? You can say '1 December 2026' or 'tomorrow'.",
    "duration_days": "How many days would you like to stay? You can also give a return date.",
    "traveller_count": "How many travelers are going, including children?",
    "budget": "What is your total group budget in INR? You can say '30k total' or give a per-person amount.",
}
SUGGESTIONS = {
    "destination": ["Help me choose a destination", "Set destination to Agra", "Set destination to Jaipur"],
    "start_date": ["Tomorrow for three days", "What details do you need?", "Show my trip summary"],
    "duration_days": ["Three days", "Five days", "A week"],
    "traveller_count": ["Just me", "Two adults", "Two adults and one child"],
    "budget": ["INR 30000 total", "INR 60000 total", "I haven't decided my budget"],
}
LABELS = {"destination": "Destination", "origin": "Starting city", "start_date": "Departure", "end_date": "Return",
          "duration_days": "Days", "traveller_count": "Travelers", "budget": "Total budget", "pace": "Pace",
          "dietary": "Dietary preference", "interests": "Interests", "hotel_style": "Stay style",
          "transport_mode": "Travel by", "seat_preference": "Seat preference", "hard_requirements": "Your requests"}


def next_field(draft):
    for name in ("destination", "start_date", "end_date", "traveller_count", "budget"):
        if not draft.get(name):
            return "duration_days" if name == "end_date" else name
    return None


def summary(work):
    rows = []
    for name, label in LABELS.items():
        value = work["draft"].get(name)
        if value:
            value = f"INR {value:,}" if name == "budget" else ", ".join(value) if isinstance(value, list) else str(value)
            rows.append(f"{label}: {value}")
    if work["draft"].get("hard_requirements"):
        rows.append("Needs verification: " + "; ".join(work["draft"]["hard_requirements"]))
    title = "Your saved outline" if work["plan_ready"] and work["confirmed"] else "Your current draft"
    return title + (":\n" + "\n".join(rows) if rows else " has no trip details yet.")


def status_reply(work):
    research = work.get("research")
    if research:
        if research["status"] == "queued":
            return "Your trip is queued behind another planning run. Your details are saved. You can close this panel and check this trip later."
        if research["status"] == "running":
            return "Your travel team is still researching. A draft normally takes 30–60 seconds; unavailable supplier details will be flagged. Your details are saved; you can close this panel and check this trip later. I haven't started another run."
        if research["status"] == "failed":
            from agents.presentation import research_failure
            names = {"Destination research", "Hotel research", "Restaurant research", "Attraction research", "A planning specialist"}
            details = " ".join(f"{item['name']}: {research_failure(item.get('reason'))}"
                               for item in research.get("failed_specialists", []) if item.get("name") in names)
            return ("The last research run could not finish checking all the details needed for your trip. " + (details + " " if details else "") +
                    "No complete plan was saved by that run. Your trip details are intact. Review them and use 'Retry research', or build a manual outline from catalog choices. Retrying may use provider credit.")
    if work["plan_ready"]:
        return "Your saved outline is ready in your Travel Book. You can review its sources, edit it, or download the PDF. Prices and availability still need supplier confirmation."
    return "No research is running for this trip. Finish and review the draft, then press 'Confirm details & start research'. Chat messages alone don't start paid research."


def _reply(row, text, awaiting=None, suggestions=None, status="ok", cards=None, estimate=None,
           per_person=_UNSET, unknown=0, choices=None, clear_hard=False):
    if per_person is _UNSET:
        per_person = row.data.get("dialogue", {}).get("per_person_budget")
    state = {"awaiting": awaiting, "suggestions": (suggestions or SUGGESTIONS.get(awaiting) or
             ["Show my trip summary", "What can you do?"])[:3], "unknown_turns": unknown}
    if per_person:
        state["per_person_budget"] = per_person
    if choices:
        state["destination_choices"] = choices
    if clear_hard:
        state["clear_hard"] = True
        state["clear_hard_conditions"] = list(row.data.get("draft", {}).get("hard_requirements", []))
    row.data = dict(row.data, dialogue=state)
    return dict(status=status, reply=text, cards=cards or [], estimate=estimate,
                awaiting=awaiting, suggestions=state["suggestions"])


def _options(db, work, text):
    from . import journey
    group = "flights" if re.search(r"\bflights?\b", text) else "experiences" if re.search(r"\b(?:experiences?|things to do)\b", text) else "stays"
    names = {d["name"].casefold(): d["name"] for d in work["options"]["destinations"]}
    names.update(PUBLIC_PLACES)
    names.update(ALIASES)
    requested = list(dict.fromkeys(name for alias, name in names.items() if re.search(r"\b" + re.escape(alias) + r"\b", text)))
    destination = requested[0] if len(requested) == 1 else work["draft"].get("destination")
    if not destination:
        return "Choose a destination first so I can show relevant options.", [], "destination"
    cards = journey.options(db, dict(work["draft"], destination=destination))[group][:3]
    if cards:
        lead = f"Here are sample {group} for {destination}. These are catalog examples, not live availability."
        if destination != work["draft"].get("destination"):
            lead += f" I haven't changed your trip destination. Set your destination to {destination} before adding one of these options."
            return lead, [dict(item, preview_only=True) for item in cards], "selection"
        return lead + " Use a Choose button to add a selection to the draft.", cards, "selection"
    if group == "flights" and not work["draft"].get("origin"):
        return "I need your starting city to match sample flight routes. Which city are you departing from?", [], "origin"
    return f"There are no sample {group} for {destination} in this catalog. I won't substitute another city's listings. Source-linked research can run after you confirm the trip, but missing supplier details will be marked for confirmation.", [], None


def chat_turn(db, row, user, text):
    from . import journey
    work = journey.present(db, row, user.id)
    current = work["draft"]
    state = deepcopy(row.data.get("dialogue", {}))
    lower = text.casefold().replace("’", "'").strip()
    slot = next_field(current)

    def finish(message, **kw):
        return _reply(row, message, **kw)

    if state.get("clear_hard") and re.fullmatch(r"(?:yes|yes,? remove (?:them|it)|confirm removal)[.! ]*", lower):
        if state.get("clear_hard_conditions") != current.get("hard_requirements", []):
            return finish("Your mandatory conditions changed after that question. Review their current list and ask again before removing them.", awaiting=slot)
        journey.update_draft(db, row, dict(current, hard_requirements=[]), row.revision)
        return finish("Removed the mandatory conditions from this draft. Review the updated details before research.", awaiting=slot)
    if state.get("clear_hard") and re.fullmatch(r"(?:no|no,? keep (?:them|it)|keep (?:them|it)|cancel)[.! ]*", lower):
        return finish("Kept your mandatory conditions. They still need verification before a plan can be confirmed.", awaiting=slot)
    if re.search(r"\b(?:remove|clear|forget)\s+(?:all |my |the )?(?:mandatory conditions|hard requirements|accessibility requirements|allergies)\b", lower):
        return finish("This will remove all mandatory conditions from the draft, including allergy or accessibility requirements. Should I remove them?",
                      awaiting="clear_hard", suggestions=["Yes, remove them", "No, keep them"], clear_hard=True)
    if re.search(r"\b(?:no longer|don't|do not)\b.*\b(?:allerg\w*|wheelchair|step-free|gluten-free|halal)\b", lower):
        return finish("I kept your existing mandatory conditions because that correction could change an important requirement. To clear them, say 'Remove my mandatory conditions', or edit them in Trip details.", awaiting=slot)
    turn = understand(text, current, work["options"]["destinations"], state)
    if turn.intent == "status":
        return finish(status_reply(work), awaiting=slot, suggestions=["Show my trip summary", "What can you do?"])
    if turn.intent in {"greeting", "help", "privacy", "booking", "acknowledge", "summary"}:
        lead = {
            "greeting": "Hi! I can help you shape a trip, compare sample options, and prepare a Travel Book.",
            "help": "I can collect or correct trip details, show catalog options, explain a saved budget, and track research. Try 'Jaipur instead of Agra', 'two adults and one child', or 'increase my budget by 5k'. Research starts only after you review and confirm; this chat doesn't book or pay.",
            "privacy": "This draft and conversation stay with your signed-in account. In TinyFish mode, research receives a generic destination task; your dates, budget, party, preferences and chat history stay on this application's backend. 'Remember preferences' is optional. Closing this panel doesn't delete a saved trip.",
            "booking": "I can prepare an indicative itinerary and Travel Book, but I can't reserve a hotel, verify availability, or make a payment in this chat. Check the source and confirm directly with the supplier before booking.",
            "acknowledge": "Your draft is saved for review; I haven't confirmed it or started another research run.",
            "summary": summary(work),
        }[turn.intent]
        estimate = None
        if turn.intent == "summary" and re.search(r"\b(?:budget|cost|price|estimate|total)\b", lower):
            if work["plan_ready"] and work["confirmed"]:
                from .travel_book import snapshot
                saved = snapshot(db, row.conversation_id, user)
                estimate = dict(budget=saved["budget"], stay=saved["stay"], flight=saved["flight"],
                                party_size=saved["brief"]["party_size"], version=saved["version"])
                lead += ("\nTrip total is awaiting supplier quotes. I can't yet confirm whether this draft fits your budget." if not saved['budget'].get('costs_complete', True) else f"\nSaved outline v{saved['version']}: INR {saved['budget']['total_inr']:,} for {saved['brief']['party_size']} travelers; listed selections only. Prices and availability need confirmation.")
            else:
                lead += "\nYour budget is a spending limit, not a verified trip cost. Itemized costs need a saved plan."
        if slot:
            lead += "\n\n" + QUESTIONS[slot]
        elif turn.intent in {"summary", "acknowledge"}:
            lead += "\nReview Trip details, then use the confirmation button when you're ready."
        return finish(lead, awaiting=slot, estimate=estimate, per_person=state.get("per_person_budget"))
    if turn.intent == "options":
        message, cards, awaiting = _options(db, work, lower)
        return finish(message, cards=cards, awaiting=awaiting)
    if turn.intent == "information":
        catalog = {d["name"].casefold(): d for d in work["options"]["destinations"]}
        names = {name: item["name"] for name, item in catalog.items()}
        names.update(PUBLIC_PLACES)
        names.update(ALIASES)
        mentioned = list(dict.fromkeys(name for alias, name in names.items() if re.search(r"\b"+re.escape(alias)+r"\b", lower)))
        if not mentioned and current.get("destination"):
            mentioned = [current["destination"]]
        if not mentioned:
            return finish("Which destination would you like to learn about? You can ask about one place or compare two.", awaiting="destination")
        descriptions = []
        for name in mentioned[:2]:
            item = catalog.get(name.casefold())
            if item:
                descriptions.append(name+" — "+item["description"]+" (Sample destination guide.)")
            elif name == "Agra":
                descriptions.append("Agra — the district's official tourism guide lists the Taj Mahal, Agra Fort, Fatehpur Sikri and Mehtab Bagh among its places to visit. Check current visiting information with the venue. Official guide: https://agra.nic.in/tourist-places/")
            else:
                descriptions.append(name+" has no description in this sample guide. I can use it as a draft destination, but I won't invent current prices, opening hours or local recommendations.")
        return finish("\n\n".join(descriptions)+"\n\nThis information hasn't changed your trip.",
                      suggestions=["Set destination to "+name for name in mentioned[:2]]+["Show my trip summary"])
    if turn.intent == "discover":
        words = re.findall(r"\b(?:relax\w*|nature|culture|food|adventure|beach\w*|mountain\w*)\b", lower)
        ranked = sorted(work["options"]["destinations"], key=lambda d: -sum(word[:5] in d.get("description", "").casefold() for word in words))[:3]
        message = "Here are a few ideas from our sample destination catalog:\n" + "\n".join(f"{d['name']}: {d.get('description', '')[:150]}" for d in ranked)
        return finish(message+"\n\nWhich destination would you like to use?", cards=ranked, awaiting="destination",
                      suggestions=["Set destination to "+d["name"] for d in ranked])
    if re.search(r"\buse my saved (?:preferences|details)\b", lower):
        turn.updates = {k: v for k, v in work["saved_preferences"].items() if k in LABELS and v is not None}
        if not turn.updates:
            return finish("I don't have saved preferences to apply. We can build this trip from what you tell me.", awaiting=slot)
        turn.notes.append("Applied the saved preferences you asked to use to this draft only.")
    # Preserve open-ended requests verbatim. The typed interpreter handles core
    # facts; requests are not restricted to a catalog of supported preference tags.
    # This is draft evidence only, never an assertion that suppliers can meet it.
    if not turn.issue and (turn.updates or turn.intent == "update"):
        requests = list(current.get("hard_requirements", []))
        if not turn.updates or "hard_requirements" in turn.updates or re.search(r"\b(?:want|need|prefer|with|without|avoid|must|please|if|also|keep|leave|include|no|not|chahiye|chaiye|nahi)\b|चाहिए|नहीं|साथ|बिना", text, re.I):
            requests.extend(text[i:i+500] for i in range(0, len(text), 500))
            turn.updates["hard_requirements"] = list(dict.fromkeys(requests))
    merged = dict(current, **turn.updates)
    if ("duration_days" in turn.updates or "start_date" in turn.updates) and "end_date" not in turn.updates:
        merged.pop("end_date", None)
    if "end_date" in turn.updates and "duration_days" not in turn.updates:
        merged.pop("duration_days", None)
    try:
        if turn.updates:
            journey.update_draft(db, row, merged, row.revision)
    except (ValidationError, HTTPException, ValueError, TypeError) as error:
        detail = str(error.detail) if isinstance(error, HTTPException) else "Please use 2–60 days, 1–30 travelers, and a positive whole-INR budget."
        return finish(detail+" Your previous draft is preserved.", status="needs_clarification", awaiting=turn.awaiting or slot)
    removed = set(row.data.get("pending_forget", []))
    for name in ("dietary", "interests", "pace"):
        if name in turn.updates:
            if not turn.updates[name] and current.get(name):
                removed.add(name)
            elif turn.updates[name]:
                removed.discard(name)
    row.data = dict(row.data, pending_forget=sorted(removed))
    work = journey.present(db, row, user.id)
    slot = next_field(work["draft"])
    pending = turn.per_person_amount or turn.pending_per_person or (state.get("per_person_budget") if "budget" not in turn.updates else None)
    if turn.issue:
        return finish(" ".join(turn.notes+[turn.issue]), status="needs_clarification", awaiting=turn.awaiting or slot,
                      suggestions=["Set destination to "+name for name in turn.choices] or None,
                      choices=turn.choices, per_person=pending)
    changed = [name for name in LABELS if (current.get(name) or None) != (work["draft"].get(name) or None)]
    if turn.updates:
        acknowledgments = []
        for name in changed:
            value = work["draft"].get(name)
            if name == "hard_requirements":
                added = [item for item in value if item not in current.get(name, [])]
                concise = "; ".join(added)
                acknowledgments.append("Added requests: " + (concise if len(concise) <= 300 else f"{len(added)} saved; the full list is in your trip draft"))
                continue
            value = f"INR {value:,} total" if name == "budget" and value else ", ".join(value) if isinstance(value, list) else value
            acknowledgments.append(f"{LABELS[name]}: {value or 'no preference'}")
        lead = "Got it — " + "; ".join(acknowledgments) + "." if changed else "I've kept those details in your draft."
        if work["draft"].get("hard_requirements"):
            lead += " Your mandatory conditions need verification before a complete plan can be confirmed."
        lead += ("\n" + " ".join(turn.notes)) if turn.notes else ""
    elif re.search(r"\b(?:plan|ready|continue|start)\b", lower):
        lead = "Let's finish the draft before starting research." if slot else summary(work)
    else:
        misses = state.get("unknown_turns", 0)+1
        lead = "I couldn't reliably match that to a trip change. Your draft is unchanged."
        if misses >= 2:
            lead += " You can also open Trip details below and enter the fields directly."
        lead += "\n\n"+QUESTIONS[slot] if slot else " Try 'Show my trip summary' or an explicit correction such as 'Set my budget to INR 40000 total'."
        return finish(lead, status="needs_clarification", awaiting=slot, unknown=misses, per_person=pending)
    lead += "\n\n"+QUESTIONS[slot] if slot else "\n\nI have the essentials. Add any other requests, or review your draft and press 'Confirm details & start research'. I'll clearly flag anything that suppliers still need to confirm."
    return finish(lead, awaiting=slot, per_person=pending)
