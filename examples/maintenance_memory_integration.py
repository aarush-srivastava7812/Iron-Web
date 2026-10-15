"""A second, synthetic application reuses the exact shared-memory API."""


def demonstrate(user, prefix="maintenance-example"):
    subject, scope = "DemoLift17", {"site_id": "synthetic-site"}
    user.add_event(
        event_id=prefix + "-initial",
        text="The approved inspection interval is seven days.",
        subject=subject,
        scope=scope,
        confirmed=True,
        claims=[
            dict(
                subject=subject,
                predicate="inspection_interval_days",
                value=7,
                kind="rule",
                scope=scope,
            )
        ],
    )
    user.wait_ready(prefix + "-initial")
    first = user.recall(
        "What is the inspection interval?", subject, "inspection_interval_days", scope
    )
    user.add_event(
        event_id=prefix + "-changed",
        text="The operator reduced the inspection interval to three days.",
        subject=subject,
        scope=scope,
        confirmed=True,
        claims=[
            dict(
                subject=subject,
                predicate="inspection_interval_days",
                value=3,
                kind="rule",
                scope=scope,
                action="supersede",
                reason="Explicit operator procedure change",
            )
        ],
    )
    user.wait_ready(prefix + "-changed")
    current = user.recall(
        "What is the current inspection interval?",
        subject,
        "inspection_interval_days",
        scope,
    )
    assert first["evidence"][0]["value"] == 7 and current["evidence"][0]["value"] == 3
    return dict(
        initial=first,
        current=current,
        scope="Synthetic second-domain reuse proof, not a real company pilot or maintenance advice.",
    )
