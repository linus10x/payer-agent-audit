#!/usr/bin/env python3
"""Block internal/unpublished notes from shipping.

Fails if any git-tracked file (a) has a name matching ``*_internal*`` or
(b) contains a do-not-publish marker ("NOT published", "do not publish",
"do not quote", "INTERNAL ONLY"). Counsel-pending working notes that leak
into a public DOI'd repo are an admission against interest — this gate
fails closed before that can happen. Exit 1 on any hit, 0 when clean.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

_NAME_MARKERS = ("_internal",)
# Specific internal-process / planning tokens that must never ship publicly.
# Kept narrow on purpose — bare "internal" is NOT a marker (it false-positives on
# "internal appeal", "internally consistent", etc.).
_CONTENT_MARKERS = (
    "not published",
    "do not publish",
    "do not quote",
    "internal only",
    "not for publication",
    "owner gate",
    "council 10/10",
    "_backing_copy",
    "cross_applied",
    "cross-applied",
    "funnel flip",
    "s3c",
    "00_control",
)
_SCANNABLE_SUFFIXES = {".md", ".py", ".txt", ".yaml", ".yml", ".rst", ".cff", ".toml"}


def _tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in out.stdout.splitlines() if line.strip()]


def main() -> int:
    this_file = Path(__file__).resolve()
    hits: list[str] = []
    for rel in _tracked_files():
        path = REPO_ROOT / rel
        if path.resolve() == this_file:
            continue
        name_l = rel.lower()
        if any(m in name_l for m in _NAME_MARKERS):
            hits.append(f"{rel}: filename matches an internal-notes pattern")
            continue
        if path.suffix.lower() not in _SCANNABLE_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8").lower()
        except (OSError, UnicodeDecodeError):
            continue
        for marker in _CONTENT_MARKERS:
            if marker in text:
                hits.append(f"{rel}: contains do-not-publish marker {marker!r}")
                break
    for h in hits:
        print(h)
    if hits:
        print(f"no-internal-notes-lint: {len(hits)} hit(s) — these must not ship")
        return 1
    print("no-internal-notes-lint: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
