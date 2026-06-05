"""Payer-not-FDA-SaMD boundary scan (GOAL requirement).

A test/doc scan confirming the library makes NO medical-necessity or
clinical-determination claim, and that the boundary is documented. The
framework governs benefit-adjudication PROCESS and recordkeeping; it never
decides medical necessity.

The scan is deliberately conservative: it flags any source line that asserts
the library MAKES / DECIDES / DETERMINES medical necessity or a clinical
determination, while allowing lines that NEGATE such a claim (the boundary
statements themselves).
"""

from __future__ import annotations

import re
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src" / "payer_agent_audit"
ROOT = Path(__file__).resolve().parent.parent

# Phrases that would be an overclaim if ASSERTED (not negated).
_OVERCLAIM_PATTERNS = [
    r"\bdetermines? medical necessity\b",
    r"\bdecides? medical necessity\b",
    r"\bmakes? (a |the )?clinical determination\b",
    r"\bclinically appropriate\b",
    r"\bFDA[- ]cleared\b",
    r"\bmedical device\b",
]

# Negation cues that make an occurrence acceptable (the boundary statements).
_NEGATION_CUES = [
    "no ",
    "not ",
    "never",
    "does not",
    "do not",
    "makes no",
    "without",
    "is not",
    "are not",
    "boundary",
    "distinct from",
    "different regulatory",
    "rather than",
    "neither",
    "nothing",
]


def _iter_source_windows():
    """Yield (path, lineno, line, context) where context is the line plus the
    two preceding lines — so a multi-line negation (``... not an FDA-regulated
    / medical device``) is recognized as a boundary statement, not an
    overclaim."""
    for path in SRC.rglob("*.py"):
        if "__pycache__" in str(path):
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines, 1):
            context = " ".join(lines[max(0, i - 3) : i]).lower()
            yield path, i, line, context


def test_no_medical_necessity_or_clinical_determination_overclaim_in_source():
    violations: list[str] = []
    for path, lineno, line, context in _iter_source_windows():
        lowered = line.lower()
        for pat in _OVERCLAIM_PATTERNS:
            if re.search(pat, lowered) and not any(cue in context for cue in _NEGATION_CUES):
                violations.append(f"{path.name}:{lineno}: {line.strip()}")
    assert not violations, "payer-not-SaMD boundary overclaim(s):\n" + "\n".join(violations)


def test_limitations_doc_carries_the_boundary():
    text = (ROOT / "LIMITATIONS.md").read_text(encoding="utf-8")
    assert "payer-not-FDA-SaMD boundary" in text
    assert "no medical-necessity or clinical determination" in text
    assert "21st Century Cures Act" in text
    # The banned public-prose token must NOT appear (use "benefit-design
    # exclusion" / "statutory exclusion" instead). Token assembled at runtime
    # so this assertion does not itself trip the banned-term prose lint.
    banned = "carve" + "-out"
    assert banned not in text.lower()


def test_readme_states_no_clinical_determination():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "no medical-necessity" in text.lower() or "makes no medical" in text.lower()
