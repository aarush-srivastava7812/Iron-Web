"""Bounded travel intake: typed values, literal evidence, per-field changes.

The model proposes claims. These checks reject the whole interpretation when a
value cannot be grounded; no partially accepted message is returned.
"""

from datetime import date
import json
import math
import re


FIELD_CONTRACT = {
    "destination": "fact: city name copied from source",
    "dates": "fact: YYYY-MM-DD to YYYY-MM-DD",
    "budget": "rule: numeric TOTAL budget, no per-person/night amount",
    "currency": "fact: explicit INR/USD/EUR/GBP",
    "departure_city": "fact: city copied from source",
    "traveller_count": "rule: explicit integer party size",
    "dietary": "rule for a trip requirement; preference for usual food preferences",
    "pace": "preference: active/relaxed if explicit",
    "interests": "preference: array of literal interests",
    "seat_preference": "preference: aisle/window",
    "accessibility": "rule: explicit step-free/wheelchair-accessible requirement",
    "max_walk_metres": "rule: integer maximum walking distance in metres",
    "avoid_boats": "rule: boolean; true for no boats, false for boats explicitly allowed",
    "max_activities_per_day": "rule: integer daily limit",
    "flight_time_preference": "rule: morning/afternoon/evening",
    "activity_preferences": "preference: literal string or array of activities",
    "hotel_preference": "preference: literal hotel style",
    "mood": "preference: explicitly stated current mood; never a diagnosis",
}
NUMBER = r"(?:\d+(?:,\d{3})*(?:\.\d+)?|zero|one|two|three|four|five|six|seven|eight|nine|ten)"
WORDS = dict(
    zip("zero one two three four five six seven eight nine ten".split(), range(11))
)
CHANGE = r"\b(?:change|lower|raise|update|reduce|increase|replace|switch)\b"
LABELS = {
    "budget": r"\bbudget\b",
    "max_walk_metres": r"\bwalk(?:ing)?\b",
    "traveller_count": r"\b(?:adults|people|party|travell?ers|travell?er count)\b",
    "max_activities_per_day": r"\bactivit(?:y|ies)\b",
    "dietary": r"\b(?:dietary|vegetarian|vegan|pescatarian|halal|kosher|gluten.free)\b",
    "accessibility": r"\b(?:step.free|wheelchair|accessibility|accessible)\b",
    "avoid_boats": r"\bboats?\b",
    "flight_time_preference": r"\bflights?\b",
    "destination": r"\b(?:destination|visit|plan|trip|travel to)\b",
    "departure_city": r"\b(?:depart|departing|departure|from)\b",
    "dates": r"\b\d{4}-\d{2}-\d{2}\b",
    "currency": r"\b(?:currency|INR|USD|EUR|GBP)\b",
    "pace": r"\bpace\b",
    "mood": r"\bmood\b",
    "seat_preference": r"\bseat\b",
    "interests": r"\binterests?\b",
    "activity_preferences": r"\bactivit(?:y|ies)|beaches|food\b",
    "hotel_preference": r"\bhotel|resort|stay\b",
}

INTAKE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["claims"],
    "properties": {
        "claims": {
            "type": "array",
            "maxItems": 32,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["predicate", "value", "action", "reason", "source_quote"],
                "properties": {
                    "predicate": {"type": "string", "enum": list(FIELD_CONTRACT)},
                    "value": {
                        "anyOf": [
                            {"type": "string", "minLength": 1},
                            {"type": "number"},
                            {"type": "boolean"},
                            {
                                "type": "array",
                                "items": {"type": "string"},
                                "minItems": 1,
                                "maxItems": 32,
                            },
                        ]
                    },
                    "action": {"type": "string", "enum": ["assert", "supersede"]},
                    "reason": {"type": "string"},
                    "source_quote": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": 1000,
                    },
                },
            },
        }
    },
}

# Discriminate on predicate: a generic union would still permit a string for
# interests or a boolean for a budget, even under constrained decoding.
_claim_schema = INTAKE_SCHEMA["properties"]["claims"]["items"]
_text_schema = {"type": "string", "minLength": 1, "maxLength": 200}
_list_schema = {"type": "array", "items": _text_schema, "minItems": 1, "maxItems": 32}
_value_schemas = {
    "budget": {"type": "number", "minimum": 0},
    "traveller_count": {"type": "integer", "minimum": 1, "maximum": 32},
    "max_walk_metres": {"type": "integer", "minimum": 0, "maximum": 100000},
    "max_activities_per_day": {"type": "integer", "minimum": 0, "maximum": 24},
    "avoid_boats": {"type": "boolean"},
    "interests": _list_schema,
    "activity_preferences": {"anyOf": [_text_schema, _list_schema]},
}
INTAKE_SCHEMA["properties"]["claims"]["items"] = {
    "anyOf": [
        dict(
            type="object",
            additionalProperties=False,
            required=_claim_schema["required"],
            properties=dict(
                _claim_schema["properties"],
                predicate={"const": predicate},
                value=_value_schemas.get(predicate, _text_schema),
            ),
        )
        for predicate in FIELD_CONTRACT
    ]
}


def number(value):
    return (
        WORDS[value.lower()]
        if value.lower() in WORDS
        else float(value.replace(",", ""))
    )


def numeric_evidence(predicate, text):
    patterns = {
        "budget": rf"\bbudget\s*(?:(?:is|to|of|now|total|:|under)\s*)*(?:(?:INR|USD|EUR|GBP)\s*)?({NUMBER})\b",
        "max_walk_metres": rf"\bwalk(?:ing)?(?:\s+(?:distance|limit|is|to|of|now|maximum|max|at|most)){{0,8}}\s*({NUMBER})\s*(?:metres|meters|m)\b",
        "traveller_count": rf"\b(?:for|party of|travell?er count(?: is| to)?)\s+({NUMBER})\s*(?:adults|people|travell?ers)?\b",
        "max_activities_per_day": rf"\b(?:at most|maximum|max)\s+({NUMBER})\s+activit(?:y|ies)\s+(?:per day|a day)\b",
    }
    return {number(m[1]) for m in re.finditer(patterns[predicate], text, re.I)}


def sentences(text):
    # Decimal points inside monetary values are not sentence boundaries.
    return re.split(r"[.!?;](?:\s+|$)|[\n]+", text)


def budget_has_unit(text):
    return any(
        numeric_evidence("budget", clause)
        and re.search(r"\bper\s+(?:person|travell?er|night|day)\b", clause, re.I)
        for sentence in sentences(text)
        for clause in re.split(r"\band\b", sentence, flags=re.I)
    )


def date_range(value):
    if not isinstance(value, str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2} to \d{4}-\d{2}-\d{2}", value
    ):
        raise ValueError("Dates need an explicit ISO date range.")
    start, end = (date.fromisoformat(v) for v in value.split(" to "))
    if end <= start:
        raise ValueError("Trip end must follow its start.")
    return start, end


def literal(value, quote):
    return bool(re.search(r"(?<!\w)" + re.escape(value) + r"(?!\w)", quote, re.I))


def validate_value(predicate, value, quote):
    if value is None or value == "" or value == []:
        raise ValueError(
            "An empty extracted value requires review of the whole message."
        )
    if predicate in {
        "budget",
        "traveller_count",
        "max_walk_metres",
        "max_activities_per_day",
    }:
        if isinstance(value, str) and re.fullmatch(r"\d+(?:\.\d+)?", value):
            value = float(value)
        if type(value) not in {int, float} or not math.isfinite(value) or value < 0:
            raise ValueError("Travel numbers must be finite and nonnegative.")
        if predicate != "budget" and (
            value != int(value)
            or value
            > (
                32
                if predicate == "traveller_count"
                else 24
                if predicate == "max_activities_per_day"
                else 100000
            )
        ):
            raise ValueError("Travel counts/distances must be bounded integers.")
        if predicate == "traveller_count" and value < 1:
            raise ValueError("A party needs at least one traveller.")
        if predicate == "budget" and budget_has_unit(quote):
            raise ValueError("A per-unit amount is not a total trip budget.")
        evidence = numeric_evidence(predicate, quote)
        if len(evidence) != 1 or value not in evidence:
            raise ValueError(
                "Extracted number is not supported by the field's source quote."
            )
        return int(value) if value == int(value) else value
    if predicate == "avoid_boats":
        if value in ("true", "false"):
            value = value == "true"
        if type(value) is not bool:
            raise ValueError("Boat constraint must be a boolean.")
        pattern = (
            r"\b(?:no boats|avoid boats|do not include boats|never.*boats)\b"
            if value
            else r"\bboats (?:are )?(?:allowed|permitted|okay)\b"
        )
        if not re.search(pattern, quote, re.I):
            raise ValueError("Boat rule is not supported by the quote.")
        return value
    if predicate in {"interests", "activity_preferences"} and isinstance(value, list):
        if len(value) > 32 or len({str(v).casefold() for v in value}) != len(value):
            raise ValueError("Preference lists must be bounded and unique.")
        return [validate_literal(v, quote) for v in value]
    if predicate == "interests":
        raise ValueError("Interests must be an array of explicit strings.")
    if predicate == "dates":
        date_range(value)
        if not all(literal(v, quote) for v in value.split(" to ")):
            raise ValueError("Dates must be copied from the source.")
        return value
    if predicate == "accessibility":
        if not isinstance(value, str):
            raise ValueError("Access requirement must be text.")
        if re.search(r"\b(?:not|no longer|do not|don't)\b", quote, re.I):
            raise ValueError("Negated access requirements need explicit review.")
        for pattern, canonical in [
            (r"step[- ]free", "step-free"),
            (r"wheelchair[- ]accessible", "wheelchair-accessible"),
        ]:
            if re.search(pattern, value, re.I) and re.search(pattern, quote, re.I):
                return canonical
        raise ValueError("Unsupported access requirement needs review.")
    value = validate_literal(value, quote)
    if predicate in {
        "dietary",
        "pace",
        "seat_preference",
        "mood",
        "flight_time_preference",
    }:
        value = value.casefold()
    enums = {
        "pace": {"active", "relaxed"},
        "mood": {"active", "relaxed"},
        "seat_preference": {"aisle", "window"},
        "flight_time_preference": {"morning", "afternoon", "evening"},
    }
    if predicate in enums and value not in enums[predicate]:
        raise ValueError("Unsupported travel label needs review.")
    if predicate == "currency":
        value = value.upper()
        if value not in {"INR", "USD", "EUR", "GBP"}:
            raise ValueError("Unsupported currency needs review.")
    if predicate in {"mood", "pace"} and not re.search(LABELS[predicate], quote, re.I):
        raise ValueError("Mood and pace must be explicitly identified by the source.")
    return value


def validate_literal(value, quote):
    if not isinstance(value, str) or not value.strip() or len(value) > 200:
        raise ValueError("Travel text must be a bounded nonempty string.")
    value = value.strip()
    if not literal(value, quote) or re.search(
        r"\b(?:not|never|no)\s+" + re.escape(value), quote, re.I
    ):
        raise ValueError("Extracted text is not supported by its source quote.")
    return value


def changed_field(predicate, text, quote):
    # Carry a change across coordinated fields in one sentence, but explicit
    # keep/prefer clauses remain assertions. Semicolons/sentences reset intent.
    for sentence in sentences(text):
        if not re.search(CHANGE, sentence, re.I) or not re.search(
            LABELS[predicate], sentence, re.I
        ):
            continue
        if re.search(
            r"\b(?:do not|don't|never)(?:\s+\w+){0,4}\s+" + CHANGE, sentence, re.I
        ):
            raise ValueError("Negated update requires review.")
        for clause in re.split(r"\band\b", sentence, flags=re.I):
            if re.search(LABELS[predicate], clause, re.I):
                if re.search(
                    r"\b(?:keep|retain|leave|prefer|usually)\b", clause, re.I
                ) and not re.search(CHANGE, clause, re.I):
                    return False
        return True
    return False


def require_complete(text, claims):
    predicates = {c["predicate"] for c in claims}
    if "budget" in predicates and budget_has_unit(text):
        raise ValueError(
            "Per-unit money needs review; a quote cannot omit its qualifier."
        )
    for claim in claims:
        predicate = claim["predicate"]
        if predicate in {
            "budget",
            "max_walk_metres",
            "traveller_count",
            "max_activities_per_day",
        }:
            evidence = numeric_evidence(predicate, text)
            if len(evidence) != 1 or claim["value"] not in evidence:
                raise ValueError("Numeric source context is ambiguous or unsupported.")
        items = claim["value"] if isinstance(claim["value"], list) else [claim["value"]]
        if predicate != "avoid_boats" and any(
            isinstance(v, str)
            and re.search(
                r"\b(?:not|never|no)(?:\s+(?:want|need|require|prefer|like|eat|have|to|a|any|longer|is|are)){0,4}\s+"
                + re.escape(v),
                text,
                re.I,
            )
            for v in items
        ):
            raise ValueError(
                "A quote omitted source negation; review the whole message."
            )
    mentioned = {
        p
        for p in (
            "budget",
            "max_walk_metres",
            "traveller_count",
            "max_activities_per_day",
        )
        if numeric_evidence(p, text)
    }
    if re.search(r"\b\d{4}-\d{2}-\d{2}\b", text):
        mentioned.add("dates")
    for p in ("dietary", "accessibility", "avoid_boats", "flight_time_preference"):
        if re.search(LABELS[p], text, re.I):
            # Ordinary profile food/interests are not an explicit no-boats rule.
            if p != "avoid_boats" or re.search(
                r"\b(?:no|avoid|never|allowed|permitted)\b", text, re.I
            ):
                mentioned.add(p)
    if not mentioned <= predicates:
        raise ValueError(
            "Interpretation omitted explicit travel fields; review the whole message."
        )
    for sentence in re.split(r"[.;\n]+|\band\b", text, flags=re.I):
        if re.search(
            r"\b(?:must|required|mandatory|need|never)\b", sentence, re.I
        ) and not any(re.search(LABELS[p], sentence, re.I) for p in predicates):
            raise ValueError(
                "Unsupported requirement needs review before any claims are saved."
            )


def hard_preference(value, quote):
    items = value if isinstance(value, list) else [value]
    for sentence in sentences(quote):
        if not any(literal(item, sentence) for item in items):
            continue
        local = [
            c
            for c in re.split(r"\band\b", sentence, flags=re.I)
            if any(literal(item, c) for item in items)
        ]
        if any(re.search(r"\b(?:prefer|usually)\b", c, re.I) for c in local):
            continue
        if re.search(
            r"\b(?:must|required|requirement|mandatory|need|never)\b", sentence, re.I
        ):
            return True
    return False


class TravelIntake:
    name = "nvidia_evaluation_travel_intake_v4_grounded"

    def __init__(self, model):
        self.model, self.count, self.normalizations = model, 0, []

    def __call__(self, text, context):
        self.count += 1
        if re.search(r"\b(?:if|unless|maybe|possibly|either)\b", text, re.I):
            return []  # Preserve the entire source as a review-needed episode.
        result = self.model.json(
            "intake-" + str(self.count),
            [
                dict(
                    role="system",
                    content=(
                        'Extract explicit travel claims as JSON {"claims":[{"predicate":...,"value":...,"action":"assert" or "supersede","reason":...,"source_quote":...}]}. '
                        "Return compact JSON without formatting whitespace. Use short field-specific source quotes, not the whole message. "
                        "Use ONLY predicate,value,action,reason,source_quote keys in each claim; no meta, kind, subject, scope or other extra keys. "
                        "Every claim requires a verbatim source_quote containing its value AND field/units/qualifiers. Copy literal source words; do not paraphrase or infer missing values. "
                        "Cover every explicit requirement, including each field in a coordinated update. If any requirement is unclear/unsupported, return claims:[] for the entire message. "
                        "Do not create empty values, diagnoses, identity/authority, protection or targets. The application supplies subject, scope and kinds. "
                        "Only explicit changes supersede; ordinary/repeated preferences assert. A usual diet is a preference. "
                        "Vocabulary: "
                        + json.dumps(FIELD_CONTRACT)
                        + ". Trusted context: "
                        + json.dumps(context)
                    ),
                ),
                dict(role="user", content=text),
            ],
            max_tokens=4000,
            schema=INTAKE_SCHEMA,
        )
        if (
            not isinstance(result, dict)
            or set(result) != {"claims"}
            or not isinstance(result["claims"], list)
            or len(result["claims"]) > 32
        ):
            raise ValueError("Invalid intake envelope.")
        if not result["claims"]:
            return []
        claims, validations = [], []
        seen = set()
        preferences = {
            "dietary",
            "pace",
            "interests",
            "seat_preference",
            "hotel_preference",
            "mood",
            "activity_preferences",
        }
        for original in result["claims"]:
            if not isinstance(original, dict) or set(original) - {
                "predicate",
                "value",
                "action",
                "reason",
                "source_quote",
            }:
                raise ValueError("Invalid intake claim fields.")
            predicate, quote = original.get("predicate"), original.get("source_quote")
            if predicate not in FIELD_CONTRACT or predicate in seen:
                raise ValueError("Unknown or duplicate intake field.")
            if (
                not isinstance(quote, str)
                or not quote.strip()
                or len(quote) > 1000
                or quote not in text
            ):
                raise ValueError("Each extracted value needs a verbatim source quote.")
            value = validate_value(predicate, original.get("value"), quote)
            action = "supersede" if changed_field(predicate, text, quote) else "assert"
            kind = "preference" if predicate in preferences else "fact"
            if predicate in {
                "budget",
                "traveller_count",
                "accessibility",
                "max_walk_metres",
                "avoid_boats",
                "max_activities_per_day",
                "flight_time_preference",
            } or (predicate in preferences and hard_preference(value, quote)):
                kind = "rule"
            claims.append(
                dict(
                    subject=context["subject"],
                    scope=dict(context.get("scope", {})),
                    predicate=predicate,
                    value=value,
                    kind=kind,
                    action=action,
                    reason=("Explicit source update. " if action == "supersede" else "")
                    + "Source quote: "
                    + quote,
                )
            )
            validations.append(
                dict(
                    predicate=predicate,
                    quote=quote,
                    before=original.get("action"),
                    after=action,
                    grounded=True,
                )
            )
            seen.add(predicate)
        require_complete(text, claims)
        self.normalizations.append(dict(intake=self.count, changes=validations))
        return claims
