#!/usr/bin/env python3
"""Reliable, src-layout-safe mutation pass (spine §7).

Applies targeted source mutations one at a time to the primitive + control
modules, runs the test suite against each mutant, and reports the kill score.
A *killed* mutant means the suite caught the change (good — strong
assertions); a *survivor* means the suite did not notice (a weak spot).

This is a deterministic, reviewable alternative to mutmut, which mishandles
this repo's src-layout (it copies the tree into ``mutants/`` and loses the
installed package). Run from the repo root:

    python3 scripts/mutation_check.py [--quick]

Exit code 0 if the kill rate meets the floor (default 0.90), else 1.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "src"

# (file, old, new) — each is a single, semantically-meaningful mutation.
# Chosen to hit comparison boundaries, boolean logic, and constants where a
# weak test would not notice. ``occurrence`` selects which match (0-based)
# when ``old`` appears multiple times.


@dataclass
class Mutation:
    rel_path: str
    old: str
    new: str
    label: str
    occurrence: int = 0


MUTATIONS: list[Mutation] = [
    # DEFCON threshold algebra
    Mutation(
        "payer_agent_audit/governance/defcon.py",
        "if target > self._level:",
        "if target >= self._level:",
        "defcon escalation boundary",
    ),
    Mutation(
        "payer_agent_audit/governance/defcon.py",
        "if (current - target) > 1:",
        "if (current - target) > 2:",
        "defcon deescalation step guard",
    ),
    Mutation(
        "payer_agent_audit/governance/defcon.py",
        "if target > current:",
        "if target < current:",
        "defcon escalation direction",
    ),
    Mutation(
        "payer_agent_audit/governance/defcon.py",
        "_HARD_STOP_STATES = frozenset({DEFCON.HALT, DEFCON.SHUTDOWN})",
        "_HARD_STOP_STATES = frozenset({DEFCON.SHUTDOWN})",
        "defcon hard-stop set excludes HALT",
    ),
    # Autonomy ladder boundaries
    Mutation(
        "payer_agent_audit/governance/autonomy_ladder.py",
        "if evidence.audit_ledger_running_for < timedelta(days=_MIN_AUDIT_LEDGER_DAYS):",
        "if evidence.audit_ledger_running_for <= timedelta(days=_MIN_AUDIT_LEDGER_DAYS):",
        "ladder ledger-tenure boundary",
    ),
    Mutation(
        "payer_agent_audit/governance/autonomy_ladder.py",
        "_MIN_AUDIT_LEDGER_DAYS = 90",
        "_MIN_AUDIT_LEDGER_DAYS = 1",
        "ladder ledger-tenure constant",
    ),
    Mutation(
        "payer_agent_audit/governance/autonomy_ladder.py",
        "if attester_norm == agent_id.strip().casefold():",
        "if attester_norm != agent_id.strip().casefold():",
        "ladder self-attestation guard inverted",
    ),
    Mutation(
        "payer_agent_audit/governance/autonomy_ladder.py",
        "if not self.value:",
        "if self.value:",
        "ladder attested-value check inverted",
    ),
    # Funding-type routing
    Mutation(
        "payer_agent_audit/payer/funding_type.py",
        "deadline=timedelta(hours=72),",
        "deadline=timedelta(hours=720),",
        "cms expedited deadline constant",
        occurrence=0,
    ),
    Mutation(
        "payer_agent_audit/payer/funding_type.py",
        "deadline=timedelta(days=15),",
        "deadline=timedelta(days=150),",
        "erisa pre-service deadline constant",
    ),
    # UM timeliness comparison
    Mutation(
        "payer_agent_audit/payer/um_timeliness.py",
        "met = elapsed <= deadline",
        "met = elapsed >= deadline",
        "um timeliness comparison inverted",
    ),
    Mutation(
        "payer_agent_audit/payer/um_timeliness.py",
        "deadline is None or deployer_deadline < deadline",
        "deadline is None or deployer_deadline > deadline",
        "um deployer-tighten-only guard inverted",
    ),
]


def _apply(path: Path, old: str, new: str, occurrence: int) -> str:
    text = path.read_text()
    idx = -1
    for _ in range(occurrence + 1):
        idx = text.find(old, idx + 1)
        if idx == -1:
            raise SystemExit(f"mutation target not found in {path}: {old!r}")
    return text[:idx] + new + text[idx + len(old) :]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--quick", action="store_true", help="run only the AL-PROBE + control tests"
    )
    parser.add_argument("--floor", type=float, default=0.90)
    args = parser.parse_args()

    test_target = (
        [
            "tests/adversarial/test_al_probes.py",
            "tests/test_payer_controls.py",
            "tests/test_primitives_units.py",
        ]
        if args.quick
        else ["tests/"]
    )

    killed = 0
    survivors: list[str] = []
    for m in MUTATIONS:
        path = SRC / m.rel_path
        original = path.read_text()
        mutated = _apply(path, m.old, m.new, m.occurrence)
        if mutated == original:
            raise SystemExit(f"mutation produced no change: {m.label}")
        path.write_text(mutated)
        try:
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    *test_target,
                    "-x",
                    "-q",
                    "-p",
                    "no:cacheprovider",
                    "--no-cov",
                    "-W",
                    "ignore::DeprecationWarning",
                    "-m",
                    "not slow",
                ],
                cwd=REPO_ROOT,
                env={"PYTHONPATH": str(SRC), "PATH": "/usr/bin:/bin"},
                capture_output=True,
                text=True,
            )
        finally:
            path.write_text(original)
        if proc.returncode != 0:
            killed += 1
            print(f"  KILLED   {m.label}")
        else:
            survivors.append(m.label)
            print(f"  SURVIVED {m.label}")

    total = len(MUTATIONS)
    rate = killed / total if total else 1.0
    print(f"\nmutation score: {killed}/{total} killed ({rate:.0%})")
    if survivors:
        print("survivors (weak spots):")
        for s in survivors:
            print(f"  - {s}")
    ok = rate >= args.floor
    print("PASS" if ok else f"FAIL (below floor {args.floor:.0%})")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
