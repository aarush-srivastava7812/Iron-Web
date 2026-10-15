"""Result validation: source freshness, booking status, grounded claims."""
from __future__ import annotations

import time

from agents.schemas import AgentResult, ValidationIssue, ValidationResult

_MAX_LIVE_AGE_S = 6 * 60 * 60  # live prices/availability older than 6h are stale


def validate_results(results: list[AgentResult]) -> ValidationResult:
    issues: list[ValidationIssue] = []
    now = int(time.time())
    for result in results:
        if result.status == "failed" and not result.errors:
            issues.append(ValidationIssue(
                severity="warning", code="failure_without_reason",
                message=f"{result.agent_id} failed without an error message",
            ))
        for evidence in result.evidence:
            age = now - evidence.retrieved_at
            if evidence.kind == "live" and age > _MAX_LIVE_AGE_S:
                issues.append(ValidationIssue(
                    severity="warning", code="stale_source",
                    message=f"{result.agent_id}: live source '{evidence.source}' data is "
                            f"{age // 60} min old; re-verify before relying on it",
                ))
            if evidence.kind == "mock":
                issues.append(ValidationIssue(
                    severity="info", code="mock_source",
                    message=f"{result.agent_id}: '{evidence.source}' returned simulated sample data",
                ))
        for budget in [result.budget] if result.budget else []:
            if budget.status == "confirmed":
                issues.append(ValidationIssue(
                    severity="error", code="unverified_confirmation",
                    message=f"{result.agent_id} reports a confirmed budget without a provider check",
                ))
    return ValidationResult(ok=not any(i.severity == "error" for i in issues), issues=issues)
