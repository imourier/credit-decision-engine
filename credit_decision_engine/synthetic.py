"""Synthetic applicants with a seed. No real person is behind any record.

A single latent "quality" factor drives the bureau, income and behaviour
fields so they are correlated the way real files tend to be, and each source
goes missing at its own rate (thin files, new users, unverifiable volatility),
which is what exercises the renormalisation in `scoring`.
"""

from __future__ import annotations

import random

from .applicant import Applicant


def _clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def applicant(rng: random.Random, i: int) -> Applicant:
    q = rng.gauss(0, 1)
    income = round(rng.lognormvariate(7.2 + 0.25 * q, 0.45), 2)
    thin_file = rng.random() < 0.15
    new_user = rng.random() < 0.20
    months = 1 + int(rng.random() * 5) if new_user else int(_clip(rng.gauss(24, 12), 3, 96))
    return Applicant(
        applicant_id=f"A{i:05d}",
        age=int(_clip(rng.gauss(38, 11), 16, 75)),
        fraud_flag=rng.random() < 0.01,
        active_default=rng.random() < (0.02 if q > -1 else 0.10),
        existing_monthly_debt=round(income * _clip(rng.gauss(0.18 - 0.05 * q, 0.10), 0, 0.9), 2),
        monthly_income=income if rng.random() > 0.03 else None,
        income_months_verified=int(_clip(rng.gauss(18 + 4 * q, 8), 0, 60)),
        income_volatility=None if rng.random() < 0.10 else round(_clip(rng.gauss(0.30 - 0.10 * q, 0.12), 0.02, 1.2), 3),
        bureau_score=None if thin_file else int(_clip(rng.gauss(640 + 70 * q, 45), 300, 850)),
        delinquencies_12m=None if thin_file else max(0, int(rng.gauss(0.6 - 0.7 * q, 0.9))),
        on_time_payment_ratio=None if new_user else round(_clip(rng.gauss(0.93 + 0.04 * q, 0.04), 0.5, 1.0), 3),
        months_on_platform=months,
        utilisation=None if thin_file else round(_clip(rng.gauss(0.45 - 0.15 * q, 0.2), 0.0, 1.4), 3),
    )


def generate(n: int, seed: int = 7) -> list[Applicant]:
    rng = random.Random(seed)
    return [applicant(rng, i) for i in range(1, n + 1)]
