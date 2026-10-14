"""`python -m credit_decision_engine --n 20` prints a decision table."""

from __future__ import annotations

import argparse
import sys

from .decision import decide
from .synthetic import generate

DECIDED_AT = "2026-01-15T12:00:00Z"   # fixed so the example output is reproducible


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="credit_decision_engine",
                                description="Decide on synthetic applicants and print the result.")
    p.add_argument("--n", type=int, default=20, help="number of synthetic applicants")
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--json", action="store_true", help="print one full decision record per line")
    args = p.parse_args(argv)

    decisions = [decide(a, DECIDED_AT) for a in generate(args.n, args.seed)]
    if args.json:
        for d in decisions:
            print(d.to_json())
        return 0

    print(f"{'applicant':<10} {'outcome':<8} {'score':>6} {'limit':>6}  {'dropped inputs':<42} reason")
    for d in decisions:
        dropped = []
        if d.scoring:
            dropped = d.scoring["dropped_blocks"] + [v for b in d.scoring["blocks"] for v in b["dropped_variables"]]
        score = f"{d.score:.1f}" if d.score is not None else "-"
        print(f"{d.applicant_id:<10} {d.outcome:<8} {score:>6} {d.limit:>6}  "
              f"{', '.join(dropped) or '-':<42} {', '.join(d.reason_codes) or '-'}")
    approved = sum(d.outcome == "APPROVE" for d in decisions)
    print(f"\n{approved} of {len(decisions)} approved")
    return 0


if __name__ == "__main__":
    sys.exit(main())
