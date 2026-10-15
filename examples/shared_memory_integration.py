"""Application UI and two independent agents share one service, not local RAM.

Provide separately configured clients with user, planner and reviewer credentials.
This example makes no bookings or model-generated travel/price claims.
"""


def demonstrate(
    user, planner, reviewer, subject="Traveller", trip="example-trip", prefix="example"
):
    scope = {"trip_id": trip}
    user.add_event(
        event_id=prefix + "-initial",
        text="My maximum travel budget is 1000.",
        subject=subject,
        scope=scope,
        confirmed=True,
    )
    user.wait_ready(prefix + "-initial")
    initial = planner.recall("What is the budget?", subject, "budget", scope)
    assert initial["answer_status"] == "supported"
    first_claim = initial["evidence"][0]["claim_id"]
    planner.call(
        "/v1/work",
        work_id=prefix + "-plan-v1",
        claim_ids=[first_claim],
        description="Draft plan using the earlier approved budget",
    )
    planner.call("/v1/work/claim", work_id=prefix + "-plan-v1")
    user.add_event(
        event_id=prefix + "-changed",
        text="Change my travel budget to 600.",
        subject=subject,
        scope=scope,
        confirmed=True,
    )
    user.wait_ready(prefix + "-changed")
    handoff = reviewer.handoff([prefix + "-plan-v1"])
    assert not handoff["can_continue"]
    current = reviewer.recall("What is the current budget?", subject, "budget", scope)
    assert current["answer_status"] == "supported"
    reviewer.call(
        "/v1/work",
        work_id=prefix + "-plan-v2",
        claim_ids=[current["evidence"][0]["claim_id"]],
        description="Revised plan using the current approved budget",
    )
    owned = reviewer.call("/v1/work/claim", work_id=prefix + "-plan-v2")["work"]
    completed = reviewer.call(
        "/v1/work/complete",
        work_id=prefix + "-plan-v2",
        lease_token=owned["lease_token"],
    )
    return dict(
        previous_plan=handoff, current_requirement=current, revised_work=completed
    )
