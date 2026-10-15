"""Small live-model agents; credentials are read from the environment only.

The intake adapter supplies an application vocabulary, not a choice of memory
tier. Existing shared-memory code alone builds cache blocks and persona cards.
"""

import json
import hashlib
import math
import time

from examples.travel_intake import (
    FIELD_CONTRACT as FIELD_CONTRACT,
    TravelIntake as TravelIntake,
)
from examples.travel_planning import (
    canonical_plan,
    canonical_review,
    check_plan,
    feasible_plans,
    requirements_from_context,
)


def parse_object(text):
    value = text.strip()
    if value.startswith("```json") and value.endswith("```"):
        value = value[7:-3].strip()
    elif value.startswith("```") and value.endswith("```"):
        value = value[3:-3].strip()

    def invalid_constant(value):
        raise ValueError("Non-finite JSON numbers are forbidden.")

    def unique_object(pairs):
        obj = {}
        for key, item in pairs:
            if key in obj:
                raise ValueError("Duplicate JSON keys are forbidden.")
            obj[key] = item
        return obj

    def finite_float(value):
        parsed = float(value)
        if not math.isfinite(parsed):
            raise ValueError("JSON numeric overflow is forbidden.")
        return parsed

    parsed = json.loads(
        value,
        parse_constant=invalid_constant,
        parse_float=finite_float,
        object_pairs_hook=unique_object,
    )
    if not isinstance(parsed, dict):
        raise ValueError("The model must return one JSON object.")
    return parsed


class NvidiaModel:
    def __init__(
        self, key, *, model="nvidia/nemotron-3.5-lightning-30b-a3b", on_record=None
    ):
        from openai import OpenAI

        self.client = OpenAI(
            api_key=key,
            base_url="https://integrate.api.nvidia.com/v1",
            timeout=60,
            max_retries=0,
        )
        self.model, self.records, self.on_record = model, [], on_record

    def json(self, label, messages, max_tokens=2200, schema=None):
        started = time.perf_counter()
        record = dict(
            label=label,
            model=self.model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=0,
            streaming=True,
            enable_thinking=False,
            top_p=0.95,
            guided_json=schema,
            guided_whitespace_pattern=r"[ \n\t]{0,1}" if schema else None,
        )
        text, first_token, finish, usage = [], None, None, None
        try:
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0,
                top_p=0.95,
                max_tokens=max_tokens,
                stream=True,
                stream_options={"include_usage": True},
                extra_body={
                    "chat_template_kwargs": {"enable_thinking": False},
                    **(
                        {
                            "guided_json": schema,
                            "guided_whitespace_pattern": r"[ \n\t]{0,1}",
                        }
                        if schema
                        else {}
                    ),
                },
            )
            with stream:
                for part in stream:
                    if part.usage:
                        usage = part.usage.model_dump()
                    if not part.choices:
                        continue
                    choice = part.choices[0]
                    if choice.delta.content:
                        if first_token is None:
                            first_token = time.perf_counter()
                        text.append(choice.delta.content)
                        if len("".join(text)) - len("".join(text).rstrip()) > 256:
                            raise ValueError("Model stalled in formatting whitespace.")
                    if choice.finish_reason:
                        finish = choice.finish_reason
            content = "".join(text)
            record.update(
                content=content,
                usage=usage,
                finish_reason=finish,
                ttft_ms=(first_token - started) * 1000 if first_token else None,
            )
            if finish == "length":
                raise ValueError("Model output reached its token limit.")
            parsed = parse_object(content)
            record["parsed"] = parsed
            return parsed
        except Exception as error:
            # Exception messages can contain provider request/account details.
            record["error_type"] = type(error).__name__
            raise
        finally:
            record["elapsed_ms"] = (time.perf_counter() - started) * 1000
            self.records.append(record)
            if self.on_record:
                self.on_record(record)


PLAN_SCHEMA = (
    'Return only JSON {"decision":"plan" or "pause", "flight_id":string or null, '
    '"hotel_id":string or null, "activity_ids":[string], "activity_days":{activity_id:"YYYY-MM-DD"}, "total_inr":number or null, '
    '"budget_inr":number, "max_walk_metres":number, "reasons":[string], "evidence_claim_ids":[string]}. '
)
REVIEW_SCHEMA = (
    'Return only JSON {"decision":"approve" or "reject" or "pause", "issues":[string], '
    '"budget_inr":number, "max_walk_metres":number, "checked_claim_ids":[string]}. '
)


def offer_catalog(fixture):
    """Keep expected answers and future scenario changes out of model inputs."""
    return {
        key: fixture[key]
        for key in (
            "quote_terms",
            "flight_offers",
            "hotel_offers",
            "activity_offers",
            "fixed_costs",
        )
    }


def plan_hash(plan):
    return hashlib.sha256(
        json.dumps(plan, sort_keys=True, allow_nan=False).encode()
    ).hexdigest()


class TravelAgent:
    def __init__(self, role, memory_client, model):
        if role not in {"planner", "reviewer"}:
            raise ValueError("Unknown travel role.")
        self.role, self.memory, self.model = role, memory_client, model

    def respond(self, label, request, fixture, draft=None):
        packet = self.memory.context(**request)
        if packet["status"] != "ready":
            return dict(status=packet["status"], context=packet, output=None)
        try:
            req = requirements_from_context(packet, fixture)
            choices = feasible_plans(fixture, req)
        except ValueError as error:
            return dict(
                status="needs_review", context=packet, output=None, reason=str(error)
            )
        instruction = (
            "Propose a plan using current memory and the supplied verified catalog combinations. "
            "Use computed totals exactly. Include all current evidence claim IDs. Never relax a hard constraint. "
            "If no combination fits, pause with empty activities, null supplier IDs and null total. "
            + PLAN_SCHEMA
            if self.role == "planner"
            else "Review the candidate against current memory and catalog. Recalculate costs; reject any violation. "
            "Use decision pause for a valid pause when no supplied combination fits. "
            + REVIEW_SCHEMA
        )
        body = (
            packet["prompt"]
            + "\nSynthetic supplier quotes:\n"
            + json.dumps(offer_catalog(fixture))
            + "\nProgram-computed feasible combinations (not model calculations):\n"
            + json.dumps(choices[:8])
        )
        if self.role == "reviewer":
            body += "\nCandidate to review:\n" + json.dumps(draft, allow_nan=False)
        raw, error_type = None, None
        try:
            raw = self.model.json(
                label,
                [
                    dict(role="system", content=instruction),
                    dict(role="user", content=body),
                ],
            )
        except Exception as error:
            # Never include provider exception text or credentials in artifacts.
            error_type = type(error).__name__
        if self.role == "planner":
            output, model_checks, source = canonical_plan(
                fixture, req, packet["claim_ids"], raw
            )
            checks = check_plan(
                output,
                fixture,
                budget=req["budget"],
                walking=req["max_walk_metres"],
                requirements=req,
            )
        else:
            output, checks = canonical_review(draft, fixture, req, packet["claim_ids"])
            model_checks = dict(
                valid_shape=isinstance(raw, dict)
                and set(raw)
                == {
                    "decision",
                    "issues",
                    "budget_inr",
                    "max_walk_metres",
                    "checked_claim_ids",
                },
                decision_matches=isinstance(raw, dict)
                and raw.get("decision") == output["decision"],
                current_limits=isinstance(raw, dict)
                and raw.get("budget_inr") == req["budget"]
                and raw.get("max_walk_metres") == req["max_walk_metres"],
            )
            source = "deterministic_constraint_review"
        valid = self.memory.validate_context(packet["context_token"])["valid"]
        if self.role == "planner" and not all(checks.values()):
            return dict(
                status="needs_review",
                context=packet,
                output=None,
                model_output=raw,
                checks=checks,
                reason="Program acceptance checks failed.",
            )
        return dict(
            status="ready" if valid else "context_changed",
            context=packet,
            output=output if valid else None,
            model_output=raw,
            model_error_type=error_type,
            decision_source=source,
            checks=checks,
            model_checks=model_checks,
            reviewed_plan_hash=plan_hash(draft) if self.role == "reviewer" else None,
        )

    def complete_reviewed(self, result, reviewer, review, fixture, work_id):
        """Only a current checked plan and its exact review may become work."""
        if self.role != "planner" or reviewer.role != "reviewer":
            raise ValueError("Use a planner and reviewer for travel acceptance.")
        if result.get("status") != "ready" or review.get("status") != "ready":
            raise ValueError("Both roles need current ready contexts.")
        plan = result.get("output")
        if (
            not isinstance(plan, dict)
            or plan.get("decision") != "plan"
            or review.get("output", {}).get("decision") != "approve"
        ):
            raise ValueError(
                "A paused/rejected plan cannot become completed travel work."
            )
        if review.get("reviewed_plan_hash") != plan_hash(plan):
            raise ValueError("Review does not cover this exact plan.")
        packet, other = result["context"], review["context"]
        if packet["subject"] != other["subject"] or packet["scope"] != other["scope"]:
            raise ValueError("Review belongs to another traveller/trip.")
        for agent, saved in ((self, packet), (reviewer, other)):
            if not agent.memory.validate_context(saved["context_token"])["valid"]:
                raise ValueError("Memory changed; obtain a new plan and review.")
            req = requirements_from_context(saved, fixture)
            approval, checks = canonical_review(plan, fixture, req, saved["claim_ids"])
            if approval["decision"] != "approve" or not all(checks.values()):
                raise ValueError("Plan fails the current acceptance checks.")
        work = self.memory.call(
            "/v1/work",
            work_id=work_id,
            claim_ids=packet["claim_ids"],
            description=json.dumps(plan, allow_nan=False),
            context_token=packet["context_token"],
        )
        owned = self.memory.call("/v1/work/claim", work_id=work_id, lease_seconds=300)
        if owned["status"] == "already_completed":
            return dict(status="completed", work_id=work["id"], already_completed=True)
        completed = self.memory.call(
            "/v1/work/complete",
            work_id=work_id,
            lease_token=owned["work"]["lease_token"],
        )
        return dict(status=completed["status"], work_id=work["id"])
