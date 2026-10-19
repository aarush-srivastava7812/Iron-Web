"""Local, conservative draft intake for TinyFish research mode.

Drafts remain unconfirmed until the traveler reviews them. This module makes
no provider calls and never turns an unrecognized message into invented facts.
"""
import datetime as dt
import re

from fastapi import HTTPException
from pydantic import ValidationError


PUBLIC_DESTINATIONS = {"agra": "Agra"}
_NUMBERS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
            "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
_COUNT = r"(\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten)"
_MONTHS = "january february march april may june july august september october november december".split()


def _number(value):
    return int(value) if value.isdigit() else _NUMBERS[value.lower()]


def draft_updates(text, current, destinations):
    lower = text.casefold()
    updates = {}
    if re.search(r"\b(?:maybe|either|unless|instead|don't|do not|not)\b", lower):
        return {}, "Please confirm the exact changes in Trip details; I haven't changed your draft from that message."
    names = {d["name"].casefold(): d["name"] for d in destinations}
    names.update(PUBLIC_DESTINATIONS)
    matches = [name for key, name in names.items() if re.search(r"(?<!\w)" + re.escape(key) + r"(?!\w)", lower)]
    origin = re.search(r"\bfrom\s+([a-z ]+?)(?=\s+(?:to|on|for)\b|[,.;]|$)", lower)
    if origin:
        start = origin[1].strip()
        aliases = {"delhi": "New Delhi", "bangalore": "Bengaluru"}
        canonical = aliases.get(start) or names.get(start)
        if canonical:
            updates["origin"] = canonical
            matches = [m for m in matches if m != canonical]
    if len(matches) == 1:
        updates["destination"] = matches[0]
    elif len(matches) > 1:
        return {}, "Which single destination should I use for this trip? Your draft is unchanged."
    duration = re.search(_COUNT + r"\s*[- ]?days?\b", lower)
    if duration:
        updates["duration_days"] = _number(duration[1])
    travelers = re.search(_COUNT + r"\s*(?:adults?|travell?ers?|people|persons?|pax|guests?)\b", lower)
    if travelers:
        updates["traveller_count"] = _number(travelers[1])
    budget = re.search(r"(?:\b(?:inr|rs\.?)\s*|₹\s*|\bbudget\s*(?:is|of|to|:)?\s*)(\d[\d,]*(?:\.\d+)?)\s*(k\b)?", lower)
    if budget:
        if re.search(r"\b(?:per person|per guest|each)\b", lower):
            return {}, "Please give the total INR budget for the whole group; I haven't assumed a group total."
        amount = float(budget[1].replace(",", "")) * (1000 if budget[2] else 1)
        if amount != int(amount):
            return {}, "Please give a total budget in whole INR. Your draft is unchanged."
        updates["budget"] = int(amount)
    dates = re.findall(r"\b\d{4}-\d{2}-\d{2}\b", text)
    if not dates:
        named = re.findall(r"\b(\d{1,2})\s+(" + "|".join(_MONTHS) + r")\s+(\d{4})\b", lower)
        try:
            dates = [dt.date(int(year), _MONTHS.index(month) + 1, int(day)).isoformat() for day, month, year in named]
        except ValueError:
            return {}, "That date isn't valid. Please enter exact dates as YYYY-MM-DD."
    if dates:
        updates["start_date"] = dates[0]
        if len(dates) == 2:
            updates["end_date"] = dates[1]
        elif len(dates) > 2:
            return {}, "Please give one departure date and one return date. Your draft is unchanged."
    for word, pace in (("relaxed", "relaxed"), ("moderate", "moderate"), ("packed", "packed")):
        if re.search(r"\b" + word + r"\b", lower):
            updates["pace"] = pace
    if "non-vegetarian" in lower or "non vegetarian" in lower:
        updates["dietary"] = "non-vegetarian"
    elif re.search(r"\bvegetarian\b", lower):
        updates["dietary"] = "vegetarian"
    interests = [word for word in ("nature", "food", "culture", "adventure", "wellness", "shopping", "photography", "spiritual")
                 if re.search(r"\b" + word + r"\b", lower)]
    if interests:
        updates["interests"] = list(dict.fromkeys([*current.get("interests", []), *interests]))
    if re.search(r"\b(?:allerg\w*|wheelchair|step-free|must|avoid|vegan|jain|gluten-free|halal)\b", lower):
        updates["hard_requirements"] = list(dict.fromkeys([*current.get("hard_requirements", []), text[:160]]))
    return updates, None


def chat_turn(db, row, user, text):
    from . import journey
    current = journey.present(db, row, user.id)
    updates, clarification = draft_updates(text, current["draft"], current["options"]["destinations"])
    if clarification:
        return dict(status="needs_clarification", reply=clarification, cards=[], estimate=None)
    merged = dict(current["draft"], **updates)
    if ("duration_days" in updates or "start_date" in updates) and "end_date" not in updates:
        merged.pop("end_date", None)
    if "end_date" in updates and "duration_days" not in updates:
        merged.pop("duration_days", None)
    try:
        if updates:
            journey.update_draft(db, row, merged, row.revision)
    except (ValidationError, HTTPException, ValueError, TypeError):
        return dict(status="needs_clarification", reply="Please check the dates, 2–60 day duration, traveler count and total INR budget. Your previous draft is preserved; you can edit Trip details below.", cards=[], estimate=None)
    work = journey.present(db, row, user.id)
    draft = work["draft"]
    destination = draft.get("destination")
    questions = []
    if not destination:
        questions.append("Which destination would you like to visit?")
    if not draft.get("start_date"):
        questions.append("What is your departure date (YYYY-MM-DD), and how many days would you like to stay?")
    elif not draft.get("end_date"):
        questions.append("How many days would you like to stay, or what is your exact return date?")
    if not draft.get("traveller_count") or not draft.get("budget"):
        questions.append("Please also give " + " and ".join(
            label for field, label in (("traveller_count", "the number of travelers"), ("budget", "your total group budget in INR"))
            if not draft.get(field)) + ".")
    reply = (f"Let's build your {destination} trip. " if destination else "I can help you build a trip. ")
    reply += " ".join(questions) if questions else "Your essentials are ready. Review Trip details below, then confirm to start TinyFish research and create your itinerary."
    if destination and not any(d["name"] == destination for d in work["options"]["destinations"]):
        reply += " This destination will use source-linked web research after you confirm the trip details."
    if draft.get("hard_requirements"):
        reply += " Your mandatory conditions are in the draft and need verification before a plan can be confirmed."
    estimate = None
    if re.search(r"\b(?:budget|cost|estimate|total|price)\b", text, re.I) and work["plan_ready"] and work["confirmed"]:
        from .travel_book import snapshot
        try:
            saved = snapshot(db, row.conversation_id, user)
            estimate = dict(budget=saved["budget"], stay=saved["stay"], flight=saved["flight"],
                            party_size=saved["brief"]["party_size"], version=saved["version"])
            reply += f" Saved outline v{saved['version']}: INR {saved['budget']['total_inr']:,} for {saved['brief']['party_size']} travelers; listed items only, prices and availability unverified."
        except HTTPException:
            pass
    cards = []
    for token, group in (("stay", "stays"), ("hotel", "stays"), ("flight", "flights"), ("experience", "experiences")):
        if token in text.casefold():
            for item in work["options"][group][:2]:
                if item not in cards:
                    cards.append(item)
    return dict(status="ok", reply=reply, cards=cards, estimate=estimate)
