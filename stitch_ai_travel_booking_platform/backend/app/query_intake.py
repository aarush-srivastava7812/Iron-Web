"""Adapter between the constraint agent and Voyara's typed dialogue parser."""
import re
from agents.query_constraint_agent import CONSTRAINT_FIELDS, QueryConstraintAgent, SOFT_FIELDS, clauses, fact_text
from .conversation_intake import classify, today, understand


def interpret(text, current, destinations, dialogue=None, *, client=None, history=(), saved=None):
    soft_facts = set()
    parsing_text = text
    choice = re.fullmatch(r"(?:(?:I (?:like|choose|prefer)|let's (?:do|choose)|go with|the)\s+)?(first|second|third)(?:\s+(?:one|option|place))?[.! ]*", text, re.I)
    choices = (dialogue or {}).get("destination_choices", [])
    if choice and len(choices) > {"first": 0, "second": 1, "third": 2}[choice[1].lower()]:
        parsing_text = "Set destination to " + choices[{"first": 0, "second": 1, "third": 2}[choice[1].lower()]]
    turn = understand(fact_text(parsing_text), current, destinations, dialogue)
    original_intent = classify(text.casefold())
    if original_intent == "discover":
        # Discovery can include facts: 'suggest a relaxing solo trip with 50k'.
        detail_text = re.sub(r"\b(?:suggest|recommend|discover|anywhere|choose a destination|not sure where|don't know where)\b", "", parsing_text, flags=re.I)
        details = understand(fact_text(detail_text), current, destinations, dialogue)
        turn.updates, turn.issue, turn.awaiting = details.updates, details.issue, details.awaiting
        turn.intent = "discover"
    if original_intent not in {"update", "discover"}:
        turn.intent = original_intent
        turn.updates = {}
    # Optional pace/interests/stay style are useful ranking inputs even when
    # their clause must be excluded from the hard-fact parser.
    if not turn.issue and turn.intent in {"update", "discover"}:
        for clause in clauses(text):
            soft_turn = understand(clause, current, destinations, dialogue)
            turn.updates.update({k: v for k, v in soft_turn.updates.items() if k in SOFT_FIELDS})
            if not fact_text(clause):
                soft_facts.update(k for k in soft_turn.updates if k in CONSTRAINT_FIELDS)
    decision = QueryConstraintAgent().run(text, current, turn=turn, client=client, history=history,
                saved=saved, destinations=[d["name"] for d in destinations], today=today().isoformat())
    # Guard mixed queries too: a model must not promote an optional budget or
    # transport merely because another clause contains a firm traveler count.
    blocked = soft_facts - turn.updates.keys()
    for name in blocked:
        decision.updates.pop(name, None)
        decision.facts.pop(name, None)
    decision.evidence = [item for item in decision.evidence if item.get("field") not in blocked]
    if turn.issue:
        decision.status = "needs_clarification"
        decision.clarification_questions = [turn.issue]
    return turn, decision
