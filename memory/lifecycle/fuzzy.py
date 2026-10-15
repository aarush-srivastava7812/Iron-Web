"""Small explainable zero-order Sugeno controller, not a probability estimator.

Inputs have overlapping low/medium/high memberships. AND uses product; rule
outputs are blended by their firing strength. Time-dependent freshness also
scales the result, so ordinary memories tend towards zero instead of a floor.
Protection and current eligibility are hard lifecycle rules outside this model.
"""

from itertools import product
import math


def memberships(value):
    value = max(0.0, min(1.0, value))
    return {
        "low": max(0.0, 1 - 2 * value),
        "medium": max(0.0, 1 - abs(2 * value - 1)),
        "high": max(0.0, 2 * value - 1),
    }


def score_memory(
    *, age_seconds, half_life_days, source_quality, independent_groups, conflicts=0
):
    if any(
        not math.isfinite(v)
        for v in (
            age_seconds,
            half_life_days,
            source_quality,
            independent_groups,
            conflicts,
        )
    ):
        raise ValueError("Fuzzy inputs must be finite.")
    if half_life_days <= 0:
        raise ValueError("Half-life must be finite and positive.")
    if not 0 <= source_quality <= 1:
        raise ValueError("Source quality must be between zero and one.")
    freshness = 2 ** (-max(0, age_seconds) / (half_life_days * 86400))
    support = min(1.0, max(0, independent_groups) / 3)
    agreement = 1 / (1 + max(0, conflicts))
    inputs = dict(
        freshness=freshness,
        quality=source_quality,
        support=support,
        agreement=agreement,
    )
    grades = {key: memberships(value) for key, value in inputs.items()}
    centers = {"low": 0.1, "medium": 0.55, "high": 1.0}
    rules = []
    for labels in product(("low", "medium", "high"), repeat=4):
        # Product over the full Cartesian rule base preserves the partition of
        # unity. With ordered linear centers this is monotone in every input;
        # minimum conjunction plus renormalization did not have that property.
        activation = math.prod(grades[key][label] for key, label in zip(inputs, labels))
        if activation == 0:
            continue
        f, q, s, a = (centers[label] for label in labels)
        consequence = 0.3 * f + 0.4 * q + 0.15 * s + 0.15 * a
        rules.append(
            dict(
                conditions=dict(zip(inputs, labels)),
                firing_strength=activation,
                output=consequence,
            )
        )
    weight = sum(rule["firing_strength"] for rule in rules)
    blended = (
        sum(r["firing_strength"] * r["output"] for r in rules) / weight if weight else 0
    )
    result = min(0.99, max(0, 0.99 * blended * freshness))
    return dict(
        score=result,
        inputs=inputs,
        memberships=grades,
        fired_rules=rules,
        method="Sugeno v2; product conjunction; monotone rule outputs; freshness scaling",
        calibrated_probability=False,
    )
