"""payer-audit CLI — verify an audit chain + show obligation routing.

Deployer-facing entry point (``payer-audit``). Stdlib-only. Subcommands:

    verify   --jsonl <path>             verify a JSONL audit chain
    info                                print version + the five primitives
    obligations --funding <t> --category <c>
                                        print the obligation routing for a
                                        (funding_type, request category)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from payer_agent_audit import __version__
from payer_agent_audit.governance.audit_chain import AuditChain, AuditChainTamperError
from payer_agent_audit.payer.funding_type import (
    FundingType,
    RequestCategory,
    obligations_for,
)

_PRIMITIVES = [
    "P1 AutonomyLadder level-gate (independent attestation, advisory-labeled)",
    "P2 SovereignVeto (mandatory authorizer in production, un-self-clearable)",
    "P3 AuditChain (genesis-branching verifier, witness anchor in production)",
    "P4 DEFCONMachine (transition-direction guard)",
    "P5 EffectiveChallengeHarness (challenger != primary, attested independence)",
]


def _cmd_info(_: argparse.Namespace) -> int:
    print(f"payer-agent-audit {__version__}")
    print("NAIC umbrella · module (a) health-payer")
    print("Five corrected-spec primitives:")
    for p in _PRIMITIVES:
        print(f"  - {p}")
    print(
        "\nReference IP for adoption — NOT a deployed control. Makes no "
        "medical-necessity / clinical determination. See LIMITATIONS.md."
    )
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    path = Path(args.jsonl)
    if not path.exists():
        print(f"error: {path} not found", file=sys.stderr)
        return 2
    try:
        chain = AuditChain(log_file=path)
        chain.verify_strict()
    except AuditChainTamperError as exc:
        print(f"TAMPER DETECTED: {exc}", file=sys.stderr)
        return 1
    print(f"OK: chain verified ({len(chain)} events), head={chain.chain_head()[:16]}...")
    return 0


def _cmd_obligations(args: argparse.Namespace) -> int:
    try:
        funding = FundingType(args.funding)
        category = RequestCategory(args.category)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    ob = obligations_for(funding, category)
    print(f"funding_type        : {ob.funding_type.value}")
    print(f"category            : {ob.category.value}")
    print(f"primary_regulator   : {ob.primary_regulator}")
    dl = ob.timeliness.deadline
    print(f"timeliness_deadline : {dl if dl is not None else 'deployer-supplied (state-specific)'}")
    print(f"timeliness_verified : {ob.timeliness.verified}")
    print(f"citation            : {ob.timeliness.citation}")
    print(f"appeal_regime       : {ob.appeal_regime}")
    print(f"external_review     : {ob.external_review_citation}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="payer-audit", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_info = sub.add_parser("info", help="print version + the five primitives")
    p_info.set_defaults(func=_cmd_info)

    p_verify = sub.add_parser("verify", help="verify a JSONL audit chain")
    p_verify.add_argument("--jsonl", required=True, help="path to the JSONL chain")
    p_verify.set_defaults(func=_cmd_verify)

    p_ob = sub.add_parser("obligations", help="print obligation routing")
    p_ob.add_argument(
        "--funding",
        required=True,
        choices=[f.value for f in FundingType],
        help="funding type",
    )
    p_ob.add_argument(
        "--category",
        required=True,
        choices=[c.value for c in RequestCategory],
        help="request category",
    )
    p_ob.set_defaults(func=_cmd_obligations)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    result: int = args.func(args)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
