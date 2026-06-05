"""Golden corpus (spine §7 credibility tier) — real public matters of record.

Each entry is a curated, version-controlled public matter of record turned
into a parametrized fixture asserting how payer-agent-audit's controls would
have GOVERNED a hypothetical scenario. Every fixture carries a primary-source
URL and is ``matters-of-record`` ONLY — it reports what a public court filing
ALLEGES, with no invented allegations and no assertion of any verdict.

Standing disclaimer for litigation entries: the inclusion of any matter is NOT
a statement that any named defendant violated any law, and a ``control_answer``
describes the control's behavior on a HYPOTHETICAL — it asserts nothing about
the actual systems, facts, or outcome of the named matter. These entries assert
the CONTROL behavior (the governance answer), never a verdict or a clinical
judgment.

This is data, not a test module (no ``test_`` prefix). It is consumed by
``test_golden_corpus.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class GoldenCase:
    case_id: str
    kind: str  # "litigation" | "regulation"
    title: str
    forum: str
    filed_or_effective: str
    primary_source_url: str
    matter_of_record: str  # neutral statement of record — no characterization
    governing_control: str  # which payer-agent-audit control speaks to it
    verified: bool = True
    extra: dict[str, str] = field(default_factory=dict)


# Litigation matters of record (status statements are sourced; we assert the
# CONTROL behavior, not the litigation outcome).
GOLDEN_LITIGATION: list[GoldenCase] = [
    GoldenCase(
        case_id="lokken-nh-predict",
        kind="litigation",
        title="Estate of Gene B. Lokken, et al. v. UnitedHealth Group, Inc., et al.",
        forum="U.S. District Court, District of Minnesota — Case 0:23-cv-03514",
        filed_or_effective="2023-11-14",
        primary_source_url="https://www.courtlistener.com/docket/68006832/",
        matter_of_record=(
            "Complaint alleges the nH Predict algorithm was used to determine "
            "Medicare Advantage post-acute-care coverage amounts. Matter of "
            "record; no verdict on the merits asserted here."
        ),
        governing_control="clinician_of_record",
        extra={
            "funding_type": "medicare_advantage",
            "control_answer": (
                "A medical-necessity denial requires an attested, licensed "
                "clinician of record who reviewed the case; the control refuses "
                "to let an autonomous agent emit such a denial without one."
            ),
        },
    ),
    GoldenCase(
        case_id="kisting-leung-pxdx",
        kind="litigation",
        title="Kisting-Leung, et al. v. Cigna Corp., et al.",
        forum="U.S. District Court, Eastern District of California — Case 2:23-cv-01477",
        filed_or_effective="2023-07-24",
        primary_source_url="https://dockets.justia.com/docket/california/caedce/2:2023cv01477/431351",
        matter_of_record=(
            "Complaint alleges the PxDx (procedure-to-diagnosis) system enabled "
            "bulk claim denials without individual file review. Matter of "
            "record; no verdict on the merits asserted here."
        ),
        governing_control="clinician_of_record",
        extra={
            "funding_type": "fully_insured",
            "control_answer": (
                "The clinician-of-record control requires an attested review "
                "(reviewed=True) per medical-necessity denial — a name attached "
                "without an attested review is rejected."
            ),
        },
    ),
]

# Regulation matters of record (effective dates / citations primary-sourced).
GOLDEN_REGULATION: list[GoldenCase] = [
    GoldenCase(
        case_id="cms-0057-f-expedited",
        kind="regulation",
        title="CMS Interoperability and Prior Authorization Final Rule (CMS-0057-F)",
        forum="Federal Register 89 FR 8758",
        filed_or_effective="2024-02-08",
        primary_source_url=(
            "https://www.cms.gov/newsroom/fact-sheets/"
            "cms-interoperability-prior-authorization-final-rule-cms-0057-f"
        ),
        matter_of_record=(
            "Expedited prior-authorization decisions: 72 hours; standard: 7 "
            "calendar days. Decision-timeframe requirements effective 2026-01-01."
        ),
        governing_control="um_timeliness",
        extra={
            "funding_type": "medicare_advantage",
            "category": "expedited_urgent",
            "deadline_hours": "72",
        },
    ),
    GoldenCase(
        case_id="erisa-2560-503-1-preservice",
        kind="regulation",
        title="ERISA claims-procedure regulation 29 CFR 2560.503-1",
        forum="DOL EBSA — 29 CFR 2560.503-1(f)(2)(iii)(A)",
        filed_or_effective="effective (current)",
        primary_source_url="https://www.law.cornell.edu/cfr/text/29/2560.503-1",
        matter_of_record=(
            "Self-funded ERISA group health plan pre-service non-urgent claim: "
            "15-day decision timeframe (one 15-day extension permitted)."
        ),
        governing_control="um_timeliness",
        extra={
            "funding_type": "self_funded_erisa",
            "category": "standard_preservice",
            "deadline_days": "15",
        },
    ),
    GoldenCase(
        case_id="erisa-2560-503-1-fair-review",
        kind="regulation",
        title="ERISA full-and-fair review 29 CFR 2560.503-1(h)",
        forum="DOL EBSA — 29 CFR 2560.503-1(h)",
        filed_or_effective="effective (current)",
        primary_source_url="https://www.law.cornell.edu/cfr/text/29/2560.503-1",
        matter_of_record=(
            "Appeal review must be conducted by a reviewer who is not the "
            "original decision-maker and gives no deference to the initial denial."
        ),
        governing_control="appeal_iro",
        extra={"funding_type": "self_funded_erisa"},
    ),
    GoldenCase(
        case_id="aca-147-136-external-review",
        kind="regulation",
        title="ACA internal/external review 45 CFR 147.136",
        forum="HHS — 45 CFR 147.136(c)/(d)",
        filed_or_effective="effective (current)",
        primary_source_url="https://www.law.cornell.edu/cfr/text/45/147.136",
        matter_of_record=(
            "Non-grandfathered plans must offer external review by an "
            "Independent Review Organization (IRO) assigned without conflict of "
            "interest."
        ),
        governing_control="appeal_iro",
        extra={"funding_type": "qhp_ffe"},
    ),
    GoldenCase(
        case_id="naic-model-ai-bulletin",
        kind="regulation",
        title="NAIC Model Bulletin: Use of AI Systems by Insurers",
        forum="NAIC — adopted by full membership",
        filed_or_effective="2023-12-04",
        primary_source_url="https://content.naic.org/insurance-topics/artificial-intelligence",
        matter_of_record=(
            "Principles-based bulletin requiring insurer AI governance programs, "
            "model-lifecycle controls, third-party AI vendor oversight, and "
            "consumer-facing transparency. At least 24 states adopted "
            "(per reg SSOT, verified 2026-06-03)."
        ),
        governing_control="umbrella",
        extra={"state_adoption_count": "24", "as_of": "2026-06-03"},
    ),
]

ALL_GOLDEN: list[GoldenCase] = GOLDEN_LITIGATION + GOLDEN_REGULATION
