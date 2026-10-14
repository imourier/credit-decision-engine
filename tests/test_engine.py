"""Tests for knock-outs, renormalisation, limit bands, capacity cap and records."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from credit_decision_engine import Applicant, Decision, decide, replay
from credit_decision_engine import limits, rules, scoring
from credit_decision_engine.synthetic import generate

AT = "2026-01-15T12:00:00Z"

GOOD = Applicant(
    applicant_id="T1", age=35, fraud_flag=False, active_default=False,
    existing_monthly_debt=100.0, monthly_income=3000.0, income_months_verified=24,
    income_volatility=0.1, bureau_score=760, delinquencies_12m=0,
    on_time_payment_ratio=0.99, months_on_platform=30, utilisation=0.3,
)


# Knock-outs ------------------------------------------------------------------

@pytest.mark.parametrize("change, code", [
    (dict(age=17), "KO01_UNDERAGE"),
    (dict(fraud_flag=True), "KO02_FRAUD_FLAG"),
    (dict(active_default=True), "KO03_ACTIVE_DEFAULT"),
    (dict(monthly_income=None), "KO04_NO_VERIFIED_INCOME"),
    (dict(monthly_income=300.0), "KO05_INCOME_BELOW_FLOOR"),
    (dict(existing_monthly_debt=2000.0), "KO06_DEBT_BURDEN"),
])
def test_each_knockout_declines_with_its_code(change, code):
    d = decide(replace(GOOD, **change), AT)
    assert d.outcome == "DECLINE" and d.reason_codes == [code]
    assert d.scoring is None, "no score is computed after a knock-out"


def test_first_failure_stops_evaluation():
    outcomes = rules.evaluate(replace(GOOD, age=16, fraud_flag=True, active_default=True))
    assert [o.code for o in outcomes] == ["KO01_UNDERAGE"]


def test_all_rules_logged_when_all_pass():
    assert [o.code for o in rules.evaluate(GOOD)] == [r.code for r in rules.KNOCKOUTS]


# Renormalisation -------------------------------------------------------------

def _weights(result):
    return {b.name: b.effective_weight for b in result.blocks}


def test_complete_file_uses_nominal_weights():
    r = scoring.score(GOOD)
    assert _weights(r) == {"bureau": 0.4, "income_stability": 0.3, "behaviour": 0.3}
    assert r.dropped_blocks == []


def test_missing_block_is_dropped_and_weights_renormalised():
    thin = replace(GOOD, bureau_score=None, delinquencies_12m=None)
    r = scoring.score(thin)
    assert r.dropped_blocks == ["bureau"]
    assert _weights(r) == {"income_stability": 0.5, "behaviour": 0.5}
    expected = round(sum(b.score * b.effective_weight for b in r.blocks), 2)
    assert r.score == expected


def test_missing_variable_renormalises_within_block_without_imputing():
    r = scoring.score(replace(GOOD, on_time_payment_ratio=None))
    behaviour = next(b for b in r.blocks if b.name == "behaviour")
    assert behaviour.dropped_variables == ["on_time_payment_ratio"]
    assert {v.name: v.effective_weight for v in behaviour.variables} == {
        "months_on_platform": 0.5, "utilisation": 0.5}
    assert "on_time_payment_ratio" not in {v.name for v in behaviour.variables}


def test_no_inputs_at_all_gives_no_score():
    empty = replace(GOOD, income_months_verified=None, income_volatility=None, bureau_score=None,
                    delinquencies_12m=None, on_time_payment_ratio=None, months_on_platform=None,
                    utilisation=None)
    d = decide(empty, AT)
    assert d.score is None and d.reason_codes == ["NO_SCORABLE_DATA"]


# Limits ----------------------------------------------------------------------

@pytest.mark.parametrize("score, band", [(100, 5000), (75, 5000), (74.99, 2500), (60, 2500),
                                         (59.99, 1000), (45, 1000), (44.99, None)])
def test_limit_bands(score, band):
    assert limits.band_for(score) == band


def test_capacity_caps_the_band():
    # income 1000, debt 100: room 300 a month, at 5% minimum payment = 6000; debt 250 -> 3000.
    assert limits.capacity_limit(1000, 100) == 6000
    r = limits.assign(80, 1000, 250)
    assert (r.band_limit, r.capacity_limit, r.final_limit, r.reason) == (5000, 3000, 3000, "CAPPED_BY_CAPACITY")


def test_capacity_below_minimum_offer_declines():
    r = limits.assign(80, 1000, 390)
    assert r.final_limit == 0 and r.reason == "DECLINE_CAPACITY"


def test_low_score_declines_before_capacity():
    assert limits.assign(30, 10000, 0).reason == "DECLINE_LOW_SCORE"


# Decision records ------------------------------------------------------------

def test_record_is_complete_and_serialisable():
    d = decide(GOOD, AT)
    data = json.loads(d.to_json())
    assert data["inputs"] == GOOD.snapshot()
    assert len(data["rule_outcomes"]) == len(rules.KNOCKOUTS)
    for block in data["scoring"]["blocks"]:
        assert {"nominal_weight", "effective_weight", "score", "variables"} <= block.keys()
        for v in block["variables"]:
            assert {"value", "points", "nominal_weight", "effective_weight"} <= v.keys()
    assert data["limit_detail"]["final_limit"] == d.limit
    assert data["policy_version"] and data["engine_version"] and data["decided_at"] == AT


def test_every_synthetic_decision_replays_from_its_own_record():
    for a in generate(200, seed=11):
        record = Decision.from_json(decide(a, AT).to_json())
        assert replay(record)


def test_tampered_record_does_not_replay():
    record = decide(GOOD, AT)
    record.inputs["bureau_score"] = 400
    assert not replay(record)
