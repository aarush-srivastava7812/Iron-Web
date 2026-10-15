"""Schedule validation: overlaps, practical transfers, trip length."""
from __future__ import annotations

from agents.schemas import DraftItinerary, TripBrief, ValidationIssue, ValidationResult


def _minutes(hhmm: str) -> int:
    try:
        hours, _, minutes = hhmm.partition(":")
        return int(hours) * 60 + int(minutes)
    except ValueError:
        return -1


def validate_itinerary(itinerary: DraftItinerary, brief: TripBrief | None = None) -> ValidationResult:
    issues: list[ValidationIssue] = []
    days = {day.day for day in itinerary.days}
    if brief is not None and brief.duration_days and days and max(days) > brief.duration_days:
        issues.append(ValidationIssue(
            severity="error", code="trip_length_mismatch",
            message=f"itinerary spans {max(days)} days but the brief asks for {brief.duration_days}",
            field="days",
        ))
    day_numbers = sorted(days)
    if day_numbers and day_numbers != list(range(day_numbers[0], day_numbers[0] + len(day_numbers))):
        issues.append(ValidationIssue(
            severity="error", code="day_gap", message="itinerary days are not contiguous",
            field="days",
        ))

    for day in itinerary.days:
        windows: list[tuple[int, int | None, str]] = []
        for stop in day.stops:
            start = _minutes(stop.start_time)
            if start < 0:
                issues.append(ValidationIssue(
                    severity="error", code="bad_time",
                    message=f"stop '{stop.title}' has an unreadable start_time",
                    field=f"day{day.day}",
                ))
                continue
            end = _minutes(stop.end_time) if stop.end_time else None
            if end is not None and end <= start:
                issues.append(ValidationIssue(
                    severity="error", code="stop_overlap",
                    message=f"stop '{stop.title}' ends before it starts",
                    field=f"day{day.day}",
                ))
            for prev_start, prev_end, prev_title in windows:
                if prev_end is None or end is None:
                    continue
                if start < prev_end and prev_start < end:
                    issues.append(ValidationIssue(
                        severity="error", code="stop_overlap",
                        message=f"day {day.day}: '{prev_title}' overlaps '{stop.title}'",
                        field=f"day{day.day}",
                    ))
            windows.append((start, end, stop.title))

        # Practical transfer: attractions/food in different locations need a gap.
        ordered = sorted(
            (s for s in day.stops if s.location and s.kind in {"attraction", "food"}),
            key=lambda s: _minutes(s.start_time),
        )
        for first, second in zip(ordered, ordered[1:]):
            if first.location != second.location and _minutes(second.start_time) - (
                _minutes(first.end_time) if first.end_time else _minutes(first.start_time)
            ) < 20:
                issues.append(ValidationIssue(
                    severity="warning", code="tight_transfer",
                    message=f"day {day.day}: only {max(0, _minutes(second.start_time) - (_minutes(first.end_time) if first.end_time else _minutes(first.start_time)))} min between "
                            f"'{first.title}' ({first.location}) and '{second.title}' ({second.location})",
                    field=f"day{day.day}",
                ))

    line_total = sum(stop.est_cost_inr for day in itinerary.days for stop in day.stops)
    if line_total != itinerary.total_est_cost_inr:
        issues.append(ValidationIssue(
            severity="error", code="itinerary_cost_mismatch",
            message=f"stop costs sum to {line_total} but total is {itinerary.total_est_cost_inr}",
            field="total_est_cost_inr",
        ))
    return ValidationResult(ok=not issues, issues=issues)
