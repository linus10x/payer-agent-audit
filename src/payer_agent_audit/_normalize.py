"""Shared identity normalization for governance guards.

The self-attestation (P1), self-clear (P2), effective-challenge (P5), and
ERISA full-and-fair-review independence (appeal/IRO) guards all compare
caller-supplied principal identifiers. A naive ``==`` (or even
``.strip().casefold()``) is defeated by Unicode confusables and zero-width
characters — e.g. a fullwidth ``ａgent`` (U+FF41) or a zero-width-space
injection reads as a *different* string and slips past the guard, letting an
agent self-attest or self-clear. ``normalize_principal_id`` closes that class
by applying NFKC compatibility folding, stripping the zero-width set, and
casefolding, so equivalent identifiers compare equal.
"""

from __future__ import annotations

import unicodedata

# Zero-width and BOM characters that ``str.strip()`` does NOT remove but that
# must not be allowed to disguise one principal as another.
_ZERO_WIDTH = dict.fromkeys(
    [
        0x200B,  # ZERO WIDTH SPACE
        0x200C,  # ZERO WIDTH NON-JOINER
        0x200D,  # ZERO WIDTH JOINER
        0x2060,  # WORD JOINER
        0xFEFF,  # ZERO WIDTH NO-BREAK SPACE / BOM
    ]
)


def normalize_principal_id(value: str) -> str:
    """Return a canonical form of a principal identifier for guard comparison.

    NFKC compatibility-folds confusables (fullwidth/compatibility forms),
    removes zero-width characters, strips surrounding whitespace, and
    casefolds. Two identifiers that a human would read as the same principal
    normalize to the same string; a blank-after-normalization id returns "".
    """
    folded = unicodedata.normalize("NFKC", value)
    folded = folded.translate(_ZERO_WIDTH)
    return folded.strip().casefold()
