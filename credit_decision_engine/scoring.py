"""Weighted scoring blocks with renormalisation over missing inputs.

The score is a weighted average of blocks; each block is a weighted average of
variables mapped to 0-100 points. All weights and breakpoints are illustrative.

Why renormalise instead of impute
---------------------------------
When an input is missing, the variable is dropped and the remaining weights in
its block are scaled to sum to one; a block with no inputs left is dropped and
the remaining block weights are scaled the same way. Nothing is imputed.

Imputation puts a number into the decision that no one observed. A median
bureau score for a thin-file applicant is a statement about other people, and
it moves the result in a direction the data does not support. Renormalising
keeps every point of the score traceable to an observed input, and the decision
record lists exactly what was dropped and the weights actually used, so a
reviewer can see that a thin-file score rests on fewer inputs. The cost is that
scores built on fewer inputs are less precise; that belongs in policy (for
example, a lower limit band), not hidden inside a made-up value.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .applicant import Applicant


def _linear(lo: float, hi: float) -> Callable[[float], float]:
    """0 points at `lo`, 100 at `hi`, clipped. Works with lo > hi (decreasing)."""
    def points(x: float) -> float:
        t = (x - lo) / (hi - lo)
        return round(100.0 * min(1.0, max(0.0, t)), 2)
    return points


def _delinquencies(n: float) -> float:
    return {0: 100.0, 1: 60.0, 2: 30.0}.get(int(n), 0.0)


@dataclass(frozen=True)
class Variable:
    name: str
    weight: float
    points: Callable[[float], float]


@dataclass(frozen=True)
class Block:
    name: str
    weight: float
    variables: tuple[Variable, ...]


BLOCKS: tuple[Block, ...] = (
    Block("bureau", 0.40, (
        Variable("bureau_score", 0.6, _linear(300, 850)),
        Variable("delinquencies_12m", 0.4, _delinquencies),
    )),
    Block("income_stability", 0.30, (
        Variable("income_months_verified", 0.5, _linear(0, 24)),
        Variable("income_volatility", 0.5, _linear(0.8, 0.0)),
    )),
    Block("behaviour", 0.30, (
        Variable("on_time_payment_ratio", 0.5, _linear(0.7, 1.0)),
        Variable("months_on_platform", 0.25, _linear(0, 36)),
        Variable("utilisation", 0.25, _linear(1.0, 0.3)),
    )),
)


@dataclass
class VariableResult:
    name: str
    value: float
    points: float
    nominal_weight: float
    effective_weight: float


@dataclass
class BlockResult:
    name: str
    nominal_weight: float
    effective_weight: float
    score: float
    variables: list[VariableResult] = field(default_factory=list)
    dropped_variables: list[str] = field(default_factory=list)


@dataclass
class ScoreResult:
    score: float | None
    blocks: list[BlockResult]
    dropped_blocks: list[str]


def _score_block(block: Block, applicant: Applicant) -> BlockResult | None:
    present = [(v, getattr(applicant, v.name)) for v in block.variables
               if getattr(applicant, v.name) is not None]
    dropped = [v.name for v in block.variables if getattr(applicant, v.name) is None]
    if not present:
        return None
    total = sum(v.weight for v, _ in present)
    results = [VariableResult(v.name, float(x), v.points(float(x)), v.weight, round(v.weight / total, 6))
               for v, x in present]
    score = round(sum(r.points * r.effective_weight for r in results), 2)
    return BlockResult(block.name, block.weight, 0.0, score, results, dropped)


def score(applicant: Applicant) -> ScoreResult:
    """Score 0-100, or None when no block has any input."""
    scored: list[BlockResult] = []
    dropped: list[str] = []
    for block in BLOCKS:
        result = _score_block(block, applicant)
        if result is None:
            dropped.append(block.name)
        else:
            scored.append(result)
    if not scored:
        return ScoreResult(None, [], dropped)
    total = sum(b.nominal_weight for b in scored)
    for b in scored:
        b.effective_weight = round(b.nominal_weight / total, 6)
    final = round(sum(b.score * b.effective_weight for b in scored), 2)
    return ScoreResult(final, scored, dropped)
