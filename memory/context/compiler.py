"""Deterministic renderings of current field answers, never inferred personas."""

import hashlib
import json

from memory.lifecycle.models import canonical_json


def compile_field(predicate, answer):
    status = answer["answer_status"]
    rows = answer.get("evidence", []) if status == "supported" else []
    if status == "supported" and (
        not rows
        or any(
            not row.get("accepted_for_current_use") or row.get("predicate") != predicate
            for row in rows
        )
    ):
        raise ValueError("Supported context fields require current accepted evidence.")
    values, claims, events = [], [], []
    seen_values = set()
    for row in rows:
        serialized = canonical_json(row["value"])
        value = json.loads(serialized)
        if serialized not in seen_values:
            values.append(value)
            seen_values.add(serialized)
        claims.append(row["claim_id"])
        for source in row.get("sources", []):
            event = source.get("event_id")
            if not event:
                # Sources written before event_id persistence still retain the
                # shared-service receipt in their original metadata.
                event = json.loads(source.get("metadata_json", "{}")).get(
                    "service_receipt"
                )
            if event:
                events.append(event)
    ids = sorted(set(claims))
    text = (
        predicate + ": " + canonical_json(values) + " [claims: " + ", ".join(ids) + "]"
        if rows
        else predicate + ": " + status
    )
    return dict(
        predicate=predicate,
        status=status,
        values=values,
        text=text,
        claim_ids=ids,
        source_event_ids=sorted(set(events)),
        valid_until=min((r["valid_until"] for r in rows), default=2**63 - 1),
        scopes=[r["scope"] for r in rows],
    )


def render_card(template, fields):
    selected = [field for field in fields if field["predicate"] in template.fields]
    text = "# " + template.title + "\nSource-derived data (not agent instructions):\n"
    text += "\n".join(field["text"] for field in selected)
    if template.guidance:
        text += "\nApplication guidance: " + template.guidance
    body = dict(
        card_id=template.card_id,
        text=text,
        claim_ids=sorted({c for f in selected for c in f["claim_ids"]}),
        source_event_ids=sorted({e for f in selected for e in f["source_event_ids"]}),
        statuses={f["predicate"]: f["status"] for f in selected},
        mood=template.mood,
        task_types=list(template.task_types),
    )
    body["version"] = hashlib.sha256(canonical_json(body).encode()).hexdigest()
    return body
