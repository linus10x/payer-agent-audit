#!/usr/bin/env python3
"""Tamper-language lint — enforces honest tamper-evidence framing.

Any line that uses "tamper-evident" / "tamper-proof" must carry a hedge on
the same line (hash-chain mechanism, within-trust-boundary, SHA-256,
detection-but-not-prevention). This keeps the public claim honest: the
ledger DETECTS tampering within its trust boundary; it does not PREVENT it.
Exit 1 on any unhedged use, 0 when clean.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

EXCLUDE_DIRS = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".mypy_cache",
        ".ruff_cache",
        ".pytest_cache",
        "htmlcov",
        "build",
        "dist",
        ".tox",
        "vendor-clauses",
    }
)

CLAIM_RE = re.compile(r"\btamper-(evident|proof)\b", re.IGNORECASE)
HEDGES = (
    "hash-chain",
    "hash chain",
    "within-trust-boundary",
    "within trust boundary",
    "within the trust boundary",
    "detection but not",
    "detects",
    "mechanism",
    "sha-256",
    "not tamper-proof",
    "not prevent",
    # honest-limitation phrasings: the ledger is NOT adversarially tamper-evident
    # on its own; the witness anchor is the control that converts it.
    "on its own",
    "internally-consistent",
    "internally consistent",
    "witness",
    "regenerat",
    "not adversarially",
    # a line that quotes a claim and marks it FALSE is honest by construction
    "false",
)
FENCE_RE = re.compile(r"^\s*```")


def _walk(root: Path):
    for path in root.rglob("*"):
        if any(part in EXCLUDE_DIRS for part in path.parts):
            continue
        if path.suffix in (".md", ".py"):
            yield path


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    this_file = Path(__file__).resolve()
    hits: list[str] = []
    for path in _walk(repo_root):
        if path.resolve() == this_file:
            continue
        in_fence = False
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if FENCE_RE.match(line):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            if CLAIM_RE.search(line):
                lowered = line.lower()
                if not any(h in lowered for h in HEDGES):
                    rel = path.relative_to(repo_root)
                    hits.append(f"{rel}:{lineno}: unhedged tamper claim: {line.strip()[:80]}")
    for h in hits:
        print(h)
    if hits:
        print(f"tamper-language-lint: {len(hits)} hit(s)")
        return 1
    print("tamper-language-lint: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
