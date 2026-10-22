"""Freshness policy for external observations, separate from preference retention.

Fresh means recently retrieved, never independently verified. Quotes are data,
not instructions. Changed wording is a review signal, not proof of contradiction.
"""

import datetime as dt
import hashlib
import json

HIGH_IMPACT = {"hours", "permits", "advisories", "transport", "accessibility", "prices"}


def utc(value):
    if isinstance(value, str):
        value = dt.datetime.fromisoformat(value)
    return (
        value.replace(tzinfo=dt.timezone.utc)
        if value.tzinfo is None
        else value.astimezone(dt.timezone.utc)
    )


def freshness(expires_at, now=None):
    try:
        return (
            "fresh"
            if utc(expires_at) > (now or dt.datetime.now(dt.timezone.utc))
            else "stale"
        )
    except (ValueError, TypeError, AttributeError):
        return "stale"


def fingerprint(statements):
    values = sorted(
        {
            (s["source_url"], " ".join(s["quote"].split()), s.get("entity_name") or "")
            for s in statements
        }
    )
    return hashlib.sha256(json.dumps(values, ensure_ascii=False).encode()).hexdigest()


def assess(statements, expires_at, *, previous_fingerprint=None, now=None):
    digest = fingerprint(statements)
    # Multiple different statements about one subject need applicability review;
    # they may be complementary. Never manufacture a factual contradiction.
    subjects = {}
    for statement in statements:
        subjects.setdefault(statement.get("entity_name") or "destination", set()).add(
            statement["quote"].strip()
        )
    return dict(
        fingerprint=digest,
        freshness=freshness(expires_at, now),
        verification="source_statements" if statements else "missing_evidence",
        changed=previous_fingerprint is not None and previous_fingerprint != digest,
        conflict_candidate=any(len(quotes) > 1 for quotes in subjects.values()),
        applicability="unknown; confirm dates and supplier conditions",
        instruction_authority=False,
    )
