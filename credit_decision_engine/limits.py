"""Credit limit: a band chosen by score, then capped by payment capacity.

The band answers "how much risk does this score justify"; the capacity cap
answers "how much can this person service". They are different questions and
the lower answer wins. Capacity assumes the line is fully drawn and the
applicant pays the minimum each month: that minimum payment, plus existing
debt service, must stay within a share of verified income.

All amounts and rates are illustrative, in generic currency units.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# (minimum score, band limit), highest first. Below the last floor: decline.
BANDS: tuple[tuple[float, int], ...] = ((75.0, 5000), (60.0, 2500), (45.0, 1000))
MIN_PAYMENT_RATE = 0.05        # minimum monthly payment on a fully drawn line
MAX_PAYMENT_TO_INCOME = 0.40   # total debt service (new instalment + existing), share of income
MIN_OFFER = 500                # a line smaller than this is not offered
ROUNDING = 100


@dataclass(frozen=True)
class LimitResult:
    band_limit: int | None
    capacity_limit: int
    final_limit: int
    reason: str | None


def band_for(score: float) -> int | None:
    for floor, limit in BANDS:
        if score >= floor:
            return limit
    return None


def capacity_limit(monthly_income: float, existing_monthly_debt: float) -> int:
    """Largest limit whose minimum payment fits the income share."""
    room = max(0.0, monthly_income * MAX_PAYMENT_TO_INCOME - existing_monthly_debt)
    return int(math.floor(room / MIN_PAYMENT_RATE / ROUNDING) * ROUNDING)


def assign(score: float, monthly_income: float, existing_monthly_debt: float) -> LimitResult:
    band = band_for(score)
    cap = capacity_limit(monthly_income, existing_monthly_debt)
    if band is None:
        return LimitResult(None, cap, 0, "DECLINE_LOW_SCORE")
    final = min(band, cap)
    if final < MIN_OFFER:
        return LimitResult(band, cap, 0, "DECLINE_CAPACITY")
    return LimitResult(band, cap, final, "CAPPED_BY_CAPACITY" if cap < band else None)
