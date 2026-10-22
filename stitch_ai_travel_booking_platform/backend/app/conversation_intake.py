"""Typed, local travel-turn interpretation. No tools, inference or memory writes.

The dialogue manager supplies the question it actually asked. Bare answers are
interpreted only against that question; dates and money use explicit arithmetic.
Unknown language is left for clarification rather than guessed into the draft.
"""
from dataclasses import dataclass, field
import datetime as dt
from decimal import Decimal
import re
from zoneinfo import ZoneInfo

PUBLIC_PLACES = {name.casefold(): name for name in (
    "Agra", "Lucknow", "Varanasi", "Ayodhya", "Amritsar", "Mathura", "Vrindavan",
    "Prayagraj", "Rishikesh", "Haridwar", "Ujjain", "Indore", "Bhopal", "Darjeeling",
    "Gangtok", "Jaisalmer", "Jodhpur", "Mount Abu", "Shimla", "Mussoorie", "Nainital",
)}
ALIASES = {"delhi": "New Delhi", "bangalore": "Bengaluru", "bombay": "Mumbai",
           "cochin": "Kochi", "alappuzha": "Alleppey", "banaras": "Varanasi", "benaras": "Varanasi"}
NUMBERS = {name: i for i, name in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty".split())}
COUNT = r"(?:\d{1,2}|" + "|".join(NUMBERS) + r")"
AMOUNT = r"(\d[\d,]*(?:\.\d+)?)\s*(k|thousand|lakh|lakhs|lac|lacs)?\b"
MONTHS = "january february march april may june july august september october november december".split()
MONTH_MAP = {key: i + 1 for i, month in enumerate(MONTHS) for key in (month, month[:3])}
MONTH = "(?:" + "|".join(sorted(MONTH_MAP, key=len, reverse=True)) + ")"
WEEKDAYS = "monday tuesday wednesday thursday friday saturday sunday".split()


def today():
    return dt.datetime.now(ZoneInfo("Asia/Kolkata")).date()


def number(value):
    return int(value) if value.isdigit() else NUMBERS[value]


@dataclass
class Turn:
    intent: str = "update"
    updates: dict = field(default_factory=dict)
    issue: str | None = None
    awaiting: str | None = None
    notes: list[str] = field(default_factory=list)
    choices: list[str] = field(default_factory=list)
    pending_per_person: int | None = None
    per_person_amount: int | None = None


def classify(text):
    if re.search(r"\b(?:do not change|don't change|keep (?:my |the )?trip unchanged)\b", text):
        return "summary"
    if re.search(r"\b(?:status|progress|stuck|timed? out|fail(?:ed)?|failure|taking so long|still working|retry research)\b", text):
        return "status"
    if re.search(r"\b(?:what can you do|how do you work|capabilities|what details)\b", text) or re.fullmatch(r"help[!. ]*", text):
        return "help"
    if re.search(r"\b(?:privacy|api key|who can see|share my|send my|remember me|is (?:this|my trip|my data) private)\b", text):
        return "privacy"
    if re.search(r"\b(?:book|reserve|pay)\b", text) and not re.search(r"\b(?:travel book|budget|plan|want|trip)\b", text):
        return "booking"
    if re.search(r"\b(?:tell me about|compare|known for|what can i see|what should i visit|how long should i)\b", text) and not re.search(r"\b(?:my trip|my budget|my draft|budget|cost|price|hotel|flight|stay)\b", text):
        return "information"
    edit = bool(re.search(r"\b(?:change|set|make|switch|move|extend|increase|reduce|remove|forget|actually|instead|use my|add)\b", text))
    if not edit and re.search(r"\b(?:show|summari[sz]e|summary|what is|what's|what are|how much|how many|tell me|do not change|don't change)\b", text):
        if re.search(r"\b(?:hotels?|stays?|flights?|experiences?|things to do)\b", text):
            return "options"
        return "summary"
    if re.search(r"\b(?:recommend|discover|suggest|not sure where|don't know where|choose a destination|surprise me|anywhere)\b", text):
        return "discover"
    if re.fullmatch(r"(?:hi|hello|hey|namaste|good morning|good evening)[!. ]*", text):
        return "greeting"
    if re.fullmatch(r"(?:thanks|thank you|great|okay|ok|yes|yep|sure|confirmed|confirm)[!. ]*", text):
        return "acknowledge"
    return "update"


def _places(text, names, turn):
    mentions = []
    for alias in sorted(names, key=len, reverse=True):
        for match in re.finditer(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", text):
            if not any(a <= match.start() < b for a, b, _ in mentions):
                mentions.append((match.start(), match.end(), names[alias]))
    mentions.sort()
    positive = []
    for start, end, place in mentions:
        prefix = text[max(0, start-35):start]
        if re.search(r"\bfrom\s*$", prefix):
            turn.updates["origin"] = place
        elif re.search(r"\b(?:not|avoid|instead of|rather than|don't want|do not want)\s*$", prefix):
            continue
        else:
            positive.append(place)
    if len(mentions) == 2 and not turn.updates.get("origin"):
        between = text[mentions[0][1]:mentions[1][0]].strip()
        if between == "to":
            turn.updates["origin"] = mentions[0][2]
            positive = [mentions[1][2]]
    positive = list(dict.fromkeys(positive))
    if positive and (len(positive) > 1 or re.search(r"\b(?:maybe|either|perhaps|unless)\b", text)):
        turn.issue = "Which destination should I use? I haven't changed the destination."
        turn.awaiting, turn.choices = "destination", positive
    elif positive:
        turn.updates["destination"] = positive[0]
    elif not mentions:
        explicit = re.search(r"\b(?:destination\s*(?:is|to|:)\s*|(?:go|travel|trip)\s+to\s+)([a-z][a-z '-]{1,50}?)(?=\s+(?:on|for|with|from|and)\b|[,.;!?]|$)", text)
        if explicit and explicit[1].strip() not in {"somewhere", "a place", "another place"}:
            turn.updates["destination"] = explicit[1].strip().title()


def _dates(text, current, turn, at):
    if re.search(r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b", text):
        turn.issue, turn.awaiting = "That numeric date can mean two different things. What is the date in YYYY-MM-DD format?", "start_date"
        return
    values = re.findall(r"\b\d{4}-\d{2}-\d{2}\b", text)
    try:
        if values:
            values = [dt.date.fromisoformat(value) for value in values]
        else:
            def named(day, month, year):
                return_year = int(current["start_date"][:4]) if current.get("start_date") and re.search(r"\b(?:return|back|end)\b", text) else at.year
                chosen = int(year) if year else return_year
                value = dt.date(chosen, MONTH_MAP[month], int(day))
                if not year and value < at:
                    value = dt.date(chosen+1, MONTH_MAP[month], int(day))
                if not year:
                    turn.notes.append(f"I interpreted that date as {value.isoformat()}.")
                return value
            ranged = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\s*(?:-|–|to|through)\s*(\d{1,2})(?:st|nd|rd|th)?\s+(" + MONTH + r")(?:\s+(\d{4}))?\b", text)
            if ranged:
                values = [named(ranged[1], ranged[3], ranged[4]), named(ranged[2], ranged[3], ranged[4])]
            else:
                matches = list(re.finditer(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(" + MONTH + r")(?:\s+(\d{4}))?\b", text))
                matches += list(re.finditer(r"\b(" + MONTH + r")\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(\d{4}))?\b", text))
                for match in sorted(matches, key=lambda m: m.start()):
                    if match[1] in MONTH_MAP:
                        values.append(named(match[2], match[1], match[3]))
                    else:
                        values.append(named(match[1], match[2], match[3]))
            if not values:
                if re.search(r"\btomorrow\b", text):
                    values = [at+dt.timedelta(days=1)]
                elif re.search(r"\btoday\b", text):
                    values = [at]
                else:
                    weekday = re.search(r"\b(?:next|this)\s+(" + "|".join(WEEKDAYS) + ")\\b", text)
                    if weekday:
                        offset = (WEEKDAYS.index(weekday[1])-at.weekday()) % 7
                        values = [at+dt.timedelta(days=offset or 7)]
                if values:
                    turn.notes.append(f"That is {values[0].isoformat()} in India time.")
        if len(values) > 2:
            raise ValueError("Too many dates")
        if values:
            if any(value < at for value in values):
                turn.issue, turn.awaiting = "That date has already passed. What future departure or return date should I use?", "start_date"
                return
            if len(values) == 1 and re.search(r"\b(?:return|back|end)\b", text):
                turn.updates["end_date"] = values[0].isoformat()
            else:
                turn.updates["start_date"] = values[0].isoformat()
                if len(values) == 2:
                    turn.updates["end_date"] = values[1].isoformat()
        elif re.search(r"\b(?:next month|next week|weekend|early|late|sometime)\b", text):
            turn.issue, turn.awaiting = "I need exact travel dates before changing the draft. What is your departure date?", "start_date"
    except ValueError:
        turn.issue, turn.awaiting = "That date isn't valid. What date should I use in YYYY-MM-DD format?", "start_date"


def _money(text, current, dialogue, turn):
    if re.search(r"\b(?:usd|eur|gbp|dollars?|euros?|pounds?)\b|[$€£]", text):
        turn.issue, turn.awaiting = "I calculate this draft in INR. What total INR budget should I use? I haven't converted that currency.", "budget"
        return
    match = re.search(r"(?:\b(?:inr|rs\.?|rupees|budget)\s*(?:is|of|to|:|about|around|under|up to|maximum|max|by)?\s*|₹\s*)" + AMOUNT, text)
    if not match:
        match = re.search(AMOUNT + r"\s*(?:inr|rupees)\b", text)
    if not match:
        match = re.search(r"\b(?:make it|spend|increase by|reduce by|lower by|raise by)\s*" + AMOUNT, text)
    if not match and dialogue.get("awaiting") == "budget":
        # Answering another detail while a budget question is pending must not
        # turn an age, day count, or year into the spending limit.
        match = re.fullmatch(r"(?:about\s+|around\s+)?" + AMOUNT + r"\s*(?:total|inr|rupees|per person|per guest|per head|each)?[.! ]*", text)
    if not match and re.fullmatch(AMOUNT, text.strip()):
        # A unit such as 30k is meaningful money; a bare 2 needs the actual question.
        candidate = re.fullmatch(AMOUNT, text.strip())
        if candidate[2]:
            match = candidate
    if not match:
        match = next((candidate for candidate in re.finditer(AMOUNT, text) if candidate[2]), None)
    if not match or re.search(r"\b(?:don't|do not)\s+(?:change|set|increase|reduce)\s+(?:my |the )?budget\b", text):
        return
    if re.match(r"\s*(?:or|to|[-–])\s*\d", text[match.end():]) or re.search(r"\bbudget\s+between\b", text):
        turn.issue, turn.awaiting = "Which single total INR budget should I use as the spending limit?", "budget"
        return
    amount = Decimal(match[1].replace(",", "")) * {None: 1, "k": 1000, "thousand": 1000,
              "lakh": 100000, "lakhs": 100000, "lac": 100000, "lacs": 100000}[match[2]]
    if amount != int(amount) or not 0 < amount <= 10**9:
        turn.issue, turn.awaiting = "Please give a positive total budget in whole INR, up to INR 1,000,000,000.", "budget"
        return
    amount = int(amount)
    if re.search(r"\b(?:per person|per guest|each|per head)\b", text) and not re.search(r"\bnot\s+(?:per person|per guest|each|per head)\b", text):
        turn.per_person_amount = amount
        party = turn.updates.get("traveller_count", current.get("traveller_count"))
        if party:
            turn.updates["budget"] = amount*party
            turn.notes.append(f"INR {amount:,} per person × {party} travelers = INR {amount*party:,} total.")
        else:
            turn.pending_per_person = amount
            turn.issue, turn.awaiting = f"INR {amount:,} per person noted. How many travelers should that cover?", "traveller_count"
    elif re.search(r"\b(?:increase|raise|reduce|decrease|lower)\b.*\bby\b", text):
        if not current.get("budget"):
            turn.issue, turn.awaiting = "I don't have a starting budget yet. What is your total group budget in INR?", "budget"
        else:
            sign = -1 if re.search(r"\b(?:reduce|decrease|lower)\b", text) else 1
            turn.updates["budget"] = current["budget"] + sign*amount
    else:
        turn.updates["budget"] = amount


def _local_language(text):
    """Normalize explicit Hindi/Hinglish vocabulary; keep original draft text.

    This parsing view never infers facts. Relative 'kal' stays ambiguous because
    it can mean yesterday or tomorrow. Romanized numbers need a countable unit.
    """
    text = text.casefold().replace("’", "'").strip().translate(str.maketrans("०१२३४५६७८९", "0123456789"))
    words = {
        "जयपुर": "jaipur", "आगरा": "agra", "दिल्ली": "delhi", "नई दिल्ली": "new delhi",
        "मुंबई": "mumbai", "मुम्बई": "mumbai", "गोवा": "goa", "केरल": "kerala",
        "वाराणसी": "varanasi", "लखनऊ": "lucknow", "अमृतसर": "amritsar", "उदयपुर": "udaipur",
        "जोधपुर": "jodhpur", "ऋषिकेश": "rishikesh", "हरिद्वार": "haridwar", "अयोध्या": "ayodhya",
        "मनाली": "manali", "शिमला": "shimla", "कोच्चि": "kochi", "बेंगलुरु": "bengaluru",
        "दिन": "days", "दिवस": "days", "din": "days", "रात": "nights", "रातें": "nights", "raat": "nights",
        "वयस्क": "adults", "लोग": "people", "व्यक्ति": "people", "log": "people",
        "बच्चा": "child", "बच्चे": "children", "बच्चों": "children", "बच्ची": "child",
        "bachcha": "child", "baccha": "child", "bachche": "children", "bache": "children",
        "शिशु": "infant", "बजट": "budget", "कुल": "total", "रुपये": "inr", "रुपए": "inr", "रुपया": "inr",
        "हजार": "thousand", "हज़ार": "thousand", "लाख": "lakh",
        "एक": "one", "दो": "two", "तीन": "three", "चार": "four", "पांच": "five", "पाँच": "five",
        "छह": "six", "सात": "seven", "आठ": "eight", "नौ": "nine", "दस": "ten",
        "जनवरी": "january", "फरवरी": "february", "फ़रवरी": "february", "मार्च": "march",
        "अप्रैल": "april", "मई": "may", "जून": "june", "जुलाई": "july", "अगस्त": "august",
        "सितंबर": "september", "सितम्बर": "september", "अक्टूबर": "october",
        "नवंबर": "november", "नवम्बर": "november", "दिसंबर": "december", "दिसम्बर": "december",
    }
    boundary = r"[\w\u0900-\u097f]"
    pattern = r"(?<!" + boundary + ")(?:" + "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True)) + r")(?!" + boundary + ")"
    text = re.sub(pattern, lambda match: words[match[0]], text)
    numbers = {"ek": "one", "do": "two", "teen": "three", "char": "four", "paanch": "five", "panch": "five", "chhe": "six", "saat": "seven", "aath": "eight", "nau": "nine", "das": "ten"}
    text = re.sub(r"\b(" + "|".join(numbers) + r")(?=\s+(?:days?|nights?|adults?|children|child|people|infants?)\b)", lambda m: numbers[m[0]], text)
    return text


def understand(text, current, destinations, dialogue=None, *, at=None):
    text = _local_language(text)
    dialogue = dialogue or {}
    turn = Turn(intent=classify(text))
    if turn.intent not in {"update", "discover"}:
        return turn
    names = {d["name"].casefold(): d["name"] for d in destinations}
    names.update(PUBLIC_PLACES)
    names.update(ALIASES)
    _places(text, names, turn)
    if dialogue.get("awaiting") == "origin" and turn.updates.get("destination") and not re.search(r"\b(?:destination|instead|visit|trip to)\b", text):
        turn.updates["origin"] = turn.updates.pop("destination")
    if turn.intent == "discover" and not turn.updates.get("destination"):
        turn.updates.clear()
        return turn
    if turn.intent == "discover":
        turn.intent = "update"
    duration = re.search(r"\b(" + COUNT + r")\s*[- ]?(days?|nights?)\b", text)
    if duration:
        count = number(duration[1]) + (1 if duration[2].startswith("night") else 0)
        if re.search(r"\b(?:extend|longer|more)\b", text):
            if current.get("duration_days"):
                count += current["duration_days"] - (1 if duration[2].startswith("night") else 0)
            else:
                turn.issue, turn.awaiting = "What should the total trip length be, in days?", "duration_days"
        turn.updates["duration_days"] = count
    elif re.search(r"\b(?:a|one|1) week\b", text):
        turn.updates["duration_days"] = 7
    counts = re.findall(r"\b(" + COUNT + r")\s*(adults?|children|child|kids?|infants?|travell?ers?|people|persons?|pax|guests?)\b", text)
    if counts:
        parts = [number(count) for count, _ in counts]
        kinds = ["adult" if kind.startswith("adult") else "child" if kind.startswith(("child", "kid")) else "infant" if kind.startswith("infant") else "total" for _, kind in counts]
        if len(parts) > 1 and ("total" in kinds or len(set(kinds)) != len(kinds) or re.search(r"\b(?:or|instead|actually)\b", text)):
            turn.issue, turn.awaiting = "How many travelers are there in total, including children?", "traveller_count"
        else:
            turn.updates["traveller_count"] = sum(parts)
    elif re.search(r"\b(?:just me|solo|only me)\b", text):
        turn.updates["traveller_count"] = 1
    elif re.search(r"\b(?:a couple|both of us|my (?:wife|husband|partner) and i)\b", text):
        turn.updates["traveller_count"] = 2
    else:
        count = re.fullmatch(r"(?:(?:actually,?|for|we are|we're|there are)\s*)?(" + COUNT + r")[.! ]*", text)
        slot = dialogue.get("awaiting")
        if count and slot in {"traveller_count", "duration_days"}:
            turn.updates[slot] = number(count[1])
    _dates(text, current, turn, at or today())
    _money(text, current, dialogue, turn)
    pending = dialogue.get("per_person_budget")
    if pending and turn.updates.get("traveller_count") and "budget" not in turn.updates:
        turn.per_person_amount = pending
        total = pending*turn.updates["traveller_count"]
        turn.updates["budget"] = total
        turn.notes.append(f"INR {pending:,} per person × {turn.updates['traveller_count']} travelers = INR {total:,} total.")
    for word, pace in (("relaxed", "relaxed"), ("slow", "relaxed"), ("moderate", "moderate"), ("packed", "packed"), ("busy", "packed")):
        if re.search(r"\b" + word + r"\b", text) and not re.search(r"\bnot\s+" + word, text):
            turn.updates["pace"] = pace
    if re.search(r"\b(?:no dietary (?:restrictions|requirements)|remove (?:my )?(?:dietary|vegetarian) (?:preference|requirement))\b", text):
        turn.updates["dietary"] = None
    elif re.search(r"\b(?:non[- ]vegetarian|not vegetarian)\b", text):
        turn.updates["dietary"] = "non-vegetarian"
    elif re.search(r"\b(?:vegetarian|veg)\b", text):
        turn.updates["dietary"] = "vegetarian"
    interests = list(current.get("interests", []))
    for interest in ("nature", "food", "culture", "adventure", "wellness", "shopping", "photography", "spiritual"):
        if re.search(r"\b" + interest + r"\b", text):
            if re.search(r"\b(?:not|no|remove|avoid)\s+" + interest + r"\b", text):
                interests = [i for i in interests if i.casefold() != interest]
            elif interest not in [i.casefold() for i in interests]:
                interests.append(interest)
    if interests != current.get("interests", []):
        turn.updates["interests"] = interests
    for field_name, words in {"hotel_style": {"luxury": "luxury", "mid-range": "mid-range", "budget hotel": "budget"},
                              "transport_mode": {"by train": "train", "by bus": "bus", "by car": "car", "by flight": "flight"},
                              "seat_preference": {"window seat": "window", "aisle seat": "aisle"}}.items():
        for word, value in words.items():
            if word in text:
                turn.updates[field_name] = value
    if re.search(r"\b(?:allerg\w*|wheelchair|step-free|must|avoid|vegan|jain|gluten-free|halal)\b", text):
        turn.updates["hard_requirements"] = list(dict.fromkeys([*current.get("hard_requirements", []), text[:160]]))
    if re.search(r"\b(?:maybe|might|perhaps)\b", text) or re.search(r"\b(?:if|unless)\b.*\b(?:budget|dates?|travelers?|travellers?|destination)\b", text):
        turn.updates = {}
        turn.pending_per_person = None
        turn.per_person_amount = None
        turn.issue = turn.issue or "That sounds provisional. What exact details should I use for this draft? I haven't changed it."
    return turn
