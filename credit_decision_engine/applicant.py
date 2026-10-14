"""The applicant record the engine decides on.

Every field the scoring stage reads is optional: thin-file and new-to-platform
applicants are normal, and the engine has to say what it did without them
rather than invent values. Knock-out fields are required.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class Applicant:
    applicant_id: str
    age: int
    fraud_flag: bool
    active_default: bool
    existing_monthly_debt: float
    monthly_income: float | None = None          # verified, monthly
    income_months_verified: int | None = None    # length of verified income history
    income_volatility: float | None = None       # coefficient of variation of monthly income
    bureau_score: int | None = None              # 300-850 scale
    delinquencies_12m: int | None = None         # 30+ days past due events, last 12 months
    on_time_payment_ratio: float | None = None   # share of obligations paid on time
    months_on_platform: int | None = None
    utilisation: float | None = None             # revolving balance / revolving limits

    def snapshot(self) -> dict[str, Any]:
        """Plain-dict copy stored with every decision."""
        return asdict(self)

    @classmethod
    def from_snapshot(cls, data: dict[str, Any]) -> "Applicant":
        return cls(**data)
