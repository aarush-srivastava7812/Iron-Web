"""Budget arithmetic validation."""
from __future__ import annotations

from agents.schemas import BudgetEstimate, TripBrief, ValidationIssue, ValidationResult


def validate_budget(budget: BudgetEstimate, brief: TripBrief | None = None) -> ValidationResult:
    issues: list[ValidationIssue] = []
    line_sum = sum(line.amount_inr for line in budget.lines)
    if line_sum != budget.total_inr:
        issues.append(ValidationIssue(
            severity="error", code="budget_total_mismatch",
            message=f"line items sum to {line_sum} but total is {budget.total_inr}",
            field="total_inr",
        ))
    if any(line.amount_inr < 0 for line in budget.lines):
        issues.append(ValidationIssue(
            severity="error", code="negative_line", message="budget lines cannot be negative",
            field="lines",
        ))
    if budget.status == "confirmed" and any(line.basis == "estimate" for line in budget.lines):
        issues.append(ValidationIssue(
            severity="warning", code="estimate_marked_confirmed",
            message="estimate-based lines cannot produce a confirmed budget",
            field="status",
        ))
    if budget.status != "confirmed" and budget.price_checked_at is None:
        issues.append(ValidationIssue(
            severity="info", code="prices_unverified",
            message="prices are estimates; no provider price check has been recorded",
        ))
    if brief is not None:
        expected = brief.effective_budget_per_person()
        if expected is not None and not budget.per_person:
            expected_total = expected * (brief.party_size or 1)
            if budget.total_inr > expected_total * 1.15:
                issues.append(ValidationIssue(
                    severity="warning", code="over_budget",
                    message=f"estimated total {budget.total_inr} exceeds the stated budget "
                            f"{expected_total} by more than 15%",
                ))
                if budget.budget_delta_inr is None:
                    budget.budget_delta_inr = budget.total_inr - expected_total
        elif expected is not None and budget.per_person and budget.total_inr > expected * 1.15:
            issues.append(ValidationIssue(
                severity="warning", code="over_budget",
                message=f"per-person estimate {budget.total_inr} exceeds the stated "
                        f"per-person budget {expected}",
            ))
            if budget.budget_delta_inr is None:
                budget.budget_delta_inr = budget.total_inr - expected
    return ValidationResult(ok=not issues, issues=issues)
