"""Knock-out rules: hard rejects evaluated in a fixed order before any scoring.

A knock-out is a condition under which no score could justify lending: legal
capacity, fraud, an open default, no verifiable income. Running them first
keeps the score honest (it is only ever computed for applicants who are
eligible at all) and makes the rejection reason unambiguous: the first rule
that fails is the reason, and evaluation stops there.

All thresholds are illustrative.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .applicant import Applicant

MIN_AGE = 18
MIN_MONTHLY_INCOME = 450.0
MAX_DEBT_TO_INCOME = 0.50


@dataclass(frozen=True)
class RuleOutcome:
    code: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class Rule:
    code: str
    description: str
    check: Callable[[Applicant], tuple[bool, str]]


def _age(a: Applicant) -> tuple[bool, str]:
    return a.age >= MIN_AGE, f"age {a.age}, minimum {MIN_AGE}"


def _fraud(a: Applicant) -> tuple[bool, str]:
    return not a.fraud_flag, "fraud flag set" if a.fraud_flag else "no fraud flag"


def _default(a: Applicant) -> tuple[bool, str]:
    return not a.active_default, "open default" if a.active_default else "no open default"


def _income_verified(a: Applicant) -> tuple[bool, str]:
    ok = a.monthly_income is not None and a.monthly_income > 0
    return ok, "verified income present" if ok else "no verified income"


def _income_floor(a: Applicant) -> tuple[bool, str]:
    income = a.monthly_income or 0.0
    return income >= MIN_MONTHLY_INCOME, f"income {income:.0f}, floor {MIN_MONTHLY_INCOME:.0f}"


def _debt_burden(a: Applicant) -> tuple[bool, str]:
    dti = a.existing_monthly_debt / (a.monthly_income or 1.0)
    return dti <= MAX_DEBT_TO_INCOME, f"debt-to-income {dti:.2f}, maximum {MAX_DEBT_TO_INCOME:.2f}"


# Order matters: identity and integrity first, then income. A rule may assume
# that every rule before it passed (the income floor assumes income exists).
KNOCKOUTS: tuple[Rule, ...] = (
    Rule("KO01_UNDERAGE", "applicant below legal age", _age),
    Rule("KO02_FRAUD_FLAG", "applicant flagged for fraud", _fraud),
    Rule("KO03_ACTIVE_DEFAULT", "applicant has an open default", _default),
    Rule("KO04_NO_VERIFIED_INCOME", "no verified income", _income_verified),
    Rule("KO05_INCOME_BELOW_FLOOR", "verified income below floor", _income_floor),
    Rule("KO06_DEBT_BURDEN", "existing debt service too high", _debt_burden),
)


def evaluate(applicant: Applicant) -> list[RuleOutcome]:
    """Run the knock-outs in order; stop at the first failure.

    Returns the outcomes of every rule actually evaluated, so the record shows
    both what failed and what was never reached.
    """
    outcomes: list[RuleOutcome] = []
    for rule in KNOCKOUTS:
        passed, detail = rule.check(applicant)
        outcomes.append(RuleOutcome(rule.code, passed, detail))
        if not passed:
            break
    return outcomes
