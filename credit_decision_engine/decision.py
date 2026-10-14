"""Orchestration: knock-outs, then scoring, then the limit, into one record.

Why store the inputs with every decision
----------------------------------------
Applicant data changes: bureaus update, income gets re-verified, behaviour
moves every month. A decision that stores only its result cannot be explained
later, because the inputs that produced it are gone. Each `Decision` carries
the exact input snapshot, every rule evaluated, every block and variable with
the weights actually used, and the policy version. `replay` recomputes a
decision from its own record; if the result differs, either the data was
tampered with or the policy changed, and both are things an auditor needs to
see.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

from . import limits, rules, scoring
from .applicant import Applicant

ENGINE_VERSION = "0.1.0"
POLICY_VERSION = "illustrative-2026.1"


@dataclass
class Decision:
    applicant_id: str
    outcome: str                      # APPROVE | DECLINE
    reason_codes: list[str]
    limit: int
    score: float | None
    decided_at: str
    engine_version: str = ENGINE_VERSION
    policy_version: str = POLICY_VERSION
    inputs: dict[str, Any] = field(default_factory=dict)
    rule_outcomes: list[dict[str, Any]] = field(default_factory=list)
    scoring: dict[str, Any] | None = None
    limit_detail: dict[str, Any] | None = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, ensure_ascii=False)

    @classmethod
    def from_json(cls, text: str) -> "Decision":
        return cls(**json.loads(text))


def decide(applicant: Applicant, decided_at: str) -> Decision:
    """Decide on one applicant. `decided_at` is passed in so replays are exact."""
    base = dict(applicant_id=applicant.applicant_id, decided_at=decided_at,
                inputs=applicant.snapshot())

    outcomes = rules.evaluate(applicant)
    rule_log = [asdict(o) for o in outcomes]
    failed = [o for o in outcomes if not o.passed]
    if failed:
        return Decision(outcome="DECLINE", reason_codes=[failed[0].code], limit=0, score=None,
                        rule_outcomes=rule_log, **base)

    result = scoring.score(applicant)
    score_log = asdict(result)
    if result.score is None:
        return Decision(outcome="DECLINE", reason_codes=["NO_SCORABLE_DATA"], limit=0, score=None,
                        rule_outcomes=rule_log, scoring=score_log, **base)

    assert applicant.monthly_income is not None  # guaranteed by the knock-outs
    lim = limits.assign(result.score, applicant.monthly_income, applicant.existing_monthly_debt)
    approved = lim.final_limit > 0
    reasons = [lim.reason] if lim.reason else []
    return Decision(outcome="APPROVE" if approved else "DECLINE", reason_codes=reasons,
                    limit=lim.final_limit, score=result.score, rule_outcomes=rule_log,
                    scoring=score_log, limit_detail=asdict(lim), **base)


def replay(record: Decision) -> bool:
    """True if the stored inputs still produce the stored decision."""
    again = decide(Applicant.from_snapshot(record.inputs), record.decided_at)
    return again.to_json() == record.to_json()
