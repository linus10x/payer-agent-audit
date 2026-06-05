#!/usr/bin/env python3
"""Banned-term lint — fails on buzzwords and public-prose leak tokens.

Scans .md and .py files (skipping fenced code blocks and the cache/build
dirs) for a curated banned list: marketing buzzwords plus the payer-specific
leak token "carve-out" (use "benefit-design exclusion" / "statutory
exclusion" instead). Exit 1 on any hit, 0 when clean. Mirrors the
finserv-agent-audit prose discipline.

Exemptions: fenced code blocks, an inline `# noqa: banned-term`, and ADR
sections that quote statutory text verbatim.
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

BANNED = [
    "delve",
    "leverage",
    "navigate",
    "journey",
    "transformative",
    "unleash",
    "unlock",
    "game-changer",
    "in today's",
    "as a leader",
    "robust",
    "cutting-edge",
    "seamless",
    # payer-specific public-prose leak token
    "carve-out",
]

FENCE_RE = re.compile(r"^\s*```")
EXEMPT_HEADINGS = ("## Regulatory Mapping", "## Statutory Quotation", "## Primary Source")


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
        exempt_section = False
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if FENCE_RE.match(line):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            if line.startswith("## "):
                exempt_section = any(line.startswith(h) for h in EXEMPT_HEADINGS)
            if exempt_section or "# noqa: banned-term" in line:
                continue
            lowered = line.lower()
            for term in BANNED:
                if term in lowered:
                    rel = path.relative_to(repo_root)
                    hits.append(f"{rel}:{lineno}: banned term {term!r}: {line.strip()[:80]}")
    for h in hits:
        print(h)
    if hits:
        print(f"banned-term-lint: {len(hits)} hit(s)")
        return 1
    print("banned-term-lint: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
