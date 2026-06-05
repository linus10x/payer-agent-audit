"""Funding-type-aware obligation mapping (module a — health-payer).

The regulatory obligations that attach to a payer coverage / utilization-
management decision depend on the plan's FUNDING TYPE — who bears the risk
and which regulator has jurisdiction. The same denial carries different
timeliness, review, and appeal obligations depending on whether the plan
is a Medicare Advantage plan (CMS), a self-funded ERISA plan (DOL), or a
fully-insured plan (state DOI). Mapping the decision to the correct
obligation set is the first governance step; getting it wrong is itself a
compliance failure.

Reg-accuracy note. Timeframes below carry a primary-source citation and a
``verified`` flag. CMS-0057-F and ERISA 29 CFR 2560.503-1 timeframes are
primary-source verified. State-DOI timeframes vary by state and are NOT
hardcoded — they are marked ``verified=False`` and must be supplied by the
deployer from their state's utilization-review statute. The library refuses
to assert a state-specific number it cannot cite.

Boundary. This maps GOVERNANCE obligations (timeliness, who-must-review,
appeal rights). It makes NO medical-necessity or clinical determination.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from enum import Enum


class FundingType(Enum):
    """How a health plan is funded — determines regulatory jurisdiction."""

    MEDICARE_ADVANTAGE = "medicare_advantage"  # CMS
    MEDICAID_MANAGED_CARE = "medicaid_managed_care"  # CMS + state
    CHIP = "chip"  # CMS + state
    QHP_FFE = "qhp_ffe"  # ACA marketplace (FFE)
    SELF_FUNDED_ERISA = "self_funded_erisa"  # DOL / ERISA
    FULLY_INSURED = "fully_insured"  # state DOI


class RequestCategory(Enum):
    """The clinical-urgency / timing category of a benefit request.

    These are TIMING categories used to select the applicable decision
    deadline — not a clinical judgment about the patient.
    """

    EXPEDITED_URGENT = "expedited_urgent"  # urgent / expedited prior auth
    STANDARD_PRESERVICE = "standard_preservice"  # non-urgent, before service
    POSTSERVICE = "postservice"  # after service rendered (claim)


@dataclass(frozen=True)
class TimelinessObligation:
    """A decision-deadline obligation for a (funding_type, category)."""

    deadline: timedelta | None  # None = deployer must supply (state-specific)
    citation: str
    citation_url: str
    verified: bool
    note: str = ""


@dataclass(frozen=True)
class ObligationSet:
    """The full obligation set that attaches to a decision."""

    funding_type: FundingType
    category: RequestCategory
    timeliness: TimelinessObligation
    requires_clinician_of_record_on_denial: bool
    appeal_regime: str
    external_review_available: bool
    external_review_citation: str
    primary_regulator: str
    citations: tuple[str, ...] = field(default_factory=tuple)


# --------------------------------------------------------------------------- #
# Primary-source-verified timeframes                                          #
# --------------------------------------------------------------------------- #
# CMS-0057-F (89 FR 8758, 2024-02-08): expedited = 72 hours; standard = 7
#   calendar days; decision-timeframe requirements effective 2026-01-01.
#   QHP-FFE issuers are EXCLUDED from the decision-timeframe requirement.
# ERISA 29 CFR 2560.503-1: urgent = 72h; pre-service non-urgent = 15 days;
#   post-service = 30 days (each with a permitted extension).
# State DOI: varies; NOT hardcoded.

_CMS_0057_URL = (
    "https://www.cms.gov/newsroom/fact-sheets/"
    "cms-interoperability-prior-authorization-final-rule-cms-0057-f"
)
_MEDICAID_438_210_URL = "https://www.law.cornell.edu/cfr/text/42/438.210"
_ERISA_503_URL = "https://www.law.cornell.edu/cfr/text/29/2560.503-1"
_ACA_147_URL = "https://www.law.cornell.edu/cfr/text/45/147.136"
_NAIC_073_URL = "https://content.naic.org/sites/default/files/model-law-073.pdf"

_CMS_TIMEFRAMES = {
    RequestCategory.EXPEDITED_URGENT: TimelinessObligation(
        deadline=timedelta(hours=72),
        citation="CMS-0057-F (89 FR 8758) expedited prior-auth decision",
        citation_url=_CMS_0057_URL,
        verified=True,
        note="Effective 2026-01-01; specific denial reason required.",
    ),
    RequestCategory.STANDARD_PRESERVICE: TimelinessObligation(
        deadline=timedelta(days=7),
        citation="CMS-0057-F (89 FR 8758) standard prior-auth decision (7 calendar days)",
        citation_url=_CMS_0057_URL,
        verified=True,
        note="Effective 2026-01-01.",
    ),
    RequestCategory.POSTSERVICE: TimelinessObligation(
        deadline=None,
        citation="CMS claims-payment timeframes (program-specific); deployer-configured",
        citation_url=_CMS_0057_URL,
        verified=False,
        note="CMS-0057-F governs prior auth; post-service claim timeframes are "
        "program-specific — supply from your contract/program rules.",
    ),
}

# Medicaid (and CHIP) managed care decision timeframes are governed by
# 42 CFR 438.210(d) — a distinct authority from Medicare Advantage. CMS-0057-F
# AMENDED 438.210(d)(1)(i): the standard timeframe is 14 calendar days for
# rating periods beginning before 2026-01-01 and 7 calendar days on/after.
# Expedited is 72 hours [(d)(2)(i)]. Verified against 42 CFR 438.210 primary
# source 2026-06-05.
_MEDICAID_TIMEFRAMES = {
    RequestCategory.EXPEDITED_URGENT: TimelinessObligation(
        deadline=timedelta(hours=72),
        citation="42 CFR 438.210(d)(2)(i) Medicaid managed-care expedited authorization",
        citation_url=_MEDICAID_438_210_URL,
        verified=True,
        note="Up to 14-calendar-day extension permitted under (d)(2)(ii).",
    ),
    RequestCategory.STANDARD_PRESERVICE: TimelinessObligation(
        deadline=timedelta(days=7),
        citation="42 CFR 438.210(d)(1)(i) Medicaid managed-care standard authorization "
        "(7 calendar days on/after 2026-01-01; 14 days before, as amended by CMS-0057-F)",
        citation_url=_MEDICAID_438_210_URL,
        verified=True,
        note="14 calendar days for rating periods beginning before 2026-01-01; "
        "7 on/after. Up to 14-day extension permitted under (d)(1)(ii).",
    ),
    RequestCategory.POSTSERVICE: TimelinessObligation(
        deadline=None,
        citation="Medicaid claims-payment timeframes (program/contract-specific)",
        citation_url=_MEDICAID_438_210_URL,
        verified=False,
        note="438.210 governs service authorization; post-service claim timeframes are "
        "program/contract-specific — supply from your state contract.",
    ),
}

_ERISA_TIMEFRAMES = {
    RequestCategory.EXPEDITED_URGENT: TimelinessObligation(
        deadline=timedelta(hours=72),
        citation="ERISA 29 CFR 2560.503-1(f)(2)(i) urgent-care claim",
        citation_url=_ERISA_503_URL,
        verified=True,
    ),
    RequestCategory.STANDARD_PRESERVICE: TimelinessObligation(
        deadline=timedelta(days=15),
        citation="ERISA 29 CFR 2560.503-1(f)(2)(iii)(A) pre-service claim (15 days)",
        citation_url=_ERISA_503_URL,
        verified=True,
        note="One 15-day extension permitted under the rule.",
    ),
    RequestCategory.POSTSERVICE: TimelinessObligation(
        deadline=timedelta(days=30),
        citation="ERISA 29 CFR 2560.503-1(f)(2)(iii)(B) post-service claim (30 days)",
        citation_url=_ERISA_503_URL,
        verified=True,
        note="One 15-day extension permitted under the rule.",
    ),
}


def _state_timeframe(category: RequestCategory) -> TimelinessObligation:
    """State-DOI timeframe placeholder — deployer must supply the value."""
    return TimelinessObligation(
        deadline=None,
        citation="State utilization-review statute (NAIC UR Model #073 framework)",
        citation_url=_NAIC_073_URL,
        verified=False,
        note="State-specific UM timeframe is NOT hardcoded. Supply your state's "
        "value (e.g. CA H&S §1367.01, TX Ins. Code Ch. 4201) from the primary "
        "source; the library will not assert a number it cannot cite.",
    )


def obligations_for(funding_type: FundingType, category: RequestCategory) -> ObligationSet:
    """Return the obligation set for a (funding_type, request category).

    This is the routing core: CMS vs ERISA vs state DOI. Getting the regime
    right is the governance act; the timeliness deadline, who-must-review,
    and appeal/external-review pathway all follow from it.
    """
    if funding_type == FundingType.MEDICARE_ADVANTAGE:
        # Medicare Advantage prior-auth timeframes: CMS-0057-F (89 FR 8758).
        timeliness = _CMS_TIMEFRAMES[category]
        return ObligationSet(
            funding_type=funding_type,
            category=category,
            timeliness=timeliness,
            requires_clinician_of_record_on_denial=True,
            appeal_regime="Medicare Advantage organization-determination appeals (42 CFR Part 422)",
            external_review_available=True,
            external_review_citation="MA independent/external review (QIC / IRE)",
            primary_regulator="CMS",
            citations=(timeliness.citation, _CMS_0057_URL),
        )
    if funding_type in (FundingType.MEDICAID_MANAGED_CARE, FundingType.CHIP):
        # Medicaid / CHIP managed-care timeframes: 42 CFR 438.210(d) — a DISTINCT
        # authority from MA (CMS-0057-F amended 438.210's standard timeframe).
        timeliness = _MEDICAID_TIMEFRAMES[category]
        return ObligationSet(
            funding_type=funding_type,
            category=category,
            timeliness=timeliness,
            requires_clinician_of_record_on_denial=True,
            appeal_regime="Medicaid managed-care grievance & appeals (42 CFR 438.400 et seq.)",
            external_review_available=True,
            external_review_citation="State fair hearing / external review",
            primary_regulator="CMS + State Medicaid agency",
            citations=(timeliness.citation, _MEDICAID_438_210_URL),
        )
    if funding_type == FundingType.SELF_FUNDED_ERISA:
        timeliness = _ERISA_TIMEFRAMES[category]
        return ObligationSet(
            funding_type=funding_type,
            category=category,
            timeliness=timeliness,
            requires_clinician_of_record_on_denial=True,
            appeal_regime="ERISA full-and-fair review (29 CFR 2560.503-1(h)) — "
            "reviewer not the original decision-maker, no deference to the denial",
            external_review_available=True,
            external_review_citation=(
                "ACA 45 CFR 147.136 external review (non-grandfathered) via IRO"
            ),
            primary_regulator="DOL (EBSA)",
            citations=(timeliness.citation, _ERISA_503_URL, _ACA_147_URL),
        )
    if funding_type == FundingType.QHP_FFE:
        # CMS-0057-F excludes QHP-FFE issuers from the decision-timeframe
        # requirement; ACA internal/external review still applies.
        return ObligationSet(
            funding_type=funding_type,
            category=category,
            timeliness=TimelinessObligation(
                deadline=None,
                citation="ACA 45 CFR 147.136 internal claims/appeals (QHP-FFE excluded "
                "from CMS-0057-F decision-timeframe requirement)",
                citation_url=_ACA_147_URL,
                # No verified DECISION deadline exists for QHP-FFE (the
                # exclusion is what is sourced, not a timeframe). `verified`
                # describes the *deadline*; with deadline=None it is False to
                # avoid a verified-True/deadline-None contradiction. The
                # exclusion itself is documented in `note`.
                verified=False,
                note="QHP-FFE issuers are EXCLUDED from the CMS-0057-F PA decision "
                "timeframe (the exclusion is primary-sourced); ACA internal-appeal "
                "timeframes apply per plan terms — supply a deployer_deadline.",
            ),
            requires_clinician_of_record_on_denial=True,
            appeal_regime="ACA 45 CFR 147.136 internal claims & appeals",
            external_review_available=True,
            external_review_citation="ACA 45 CFR 147.136 external review via IRO",
            primary_regulator="HHS / CMS (FFE) + state",
            citations=(_ACA_147_URL,),
        )
    # FULLY_INSURED -> state DOI
    timeliness = _state_timeframe(category)
    return ObligationSet(
        funding_type=funding_type,
        category=category,
        timeliness=timeliness,
        requires_clinician_of_record_on_denial=True,
        appeal_regime="State grievance procedure (NAIC Health Carrier Grievance "
        "Procedure Model Act framework)",
        external_review_available=True,
        external_review_citation="ACA 45 CFR 147.136 / state external review via IRO",
        primary_regulator="State Department of Insurance",
        citations=(timeliness.citation, _NAIC_073_URL, _ACA_147_URL),
    )
