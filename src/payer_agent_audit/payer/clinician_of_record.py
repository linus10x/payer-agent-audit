"""Clinician-of-record-on-denial control (module a — health-payer).

An adverse benefit determination (a denial) that turns on medical judgment
must have a CLINICIAN OF RECORD — a licensed clinician who made or reviewed
the determination. This control records and ENFORCES the presence of that
attestation before an autonomous agent may emit a medical-necessity denial.

This is the governance answer to publicly-reported matters in which
algorithmic UM systems were alleged to have denied care without individual
clinician review. The control does NOT decide medical necessity — it refuses
to let a denial that requires clinical judgment be issued without an
attested, licensed human clinician on the record. (Specific public dockets,
framed as matters of record with no merit assertion, live only in the
test golden corpus, not in this module.)

Boundary. The clinician's medical judgment is the clinician's; this control
governs the PRESENCE and ATTESTATION of that judgment, not its content.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from payer_agent_audit.schemas.audit_event import AuditEventType, AutonomyLevel

if TYPE_CHECKING:
    from payer_agent_audit.governance.audit_chain import AuditChain


class ClinicianOfRecordMissingError(RuntimeError):
    """Raised when a medical-judgment denial lacks a valid clinician of record."""


@dataclass(frozen=True)
class ClinicianOfRecord:
    """A licensed clinician who reviewed/made an adverse determination.

    ``reviewed`` must be True — the clinician must attest they actually
    reviewed the case, not merely that their name is attached.
    ``same_or_similar_specialty`` records whether the reviewer is in the
    same/similar specialty (a common statutory requirement for
    medical-necessity denials). It is ATTESTED, not adjudicated; by default it
    is recorded but not gated, because the specialty-match requirement is
    state-specific. A deployer in a state that requires it can enforce the gate
    via ``attest_denial(..., require_specialty_match=True)``.
    """

    clinician_name: str
    license_number: str
    npi: str
    reviewed: bool
    same_or_similar_specialty: bool = False

    def is_valid(self, *, require_specialty_match: bool = False) -> tuple[bool, str]:
        if not self.clinician_name.strip():
            return False, "clinician_name is empty/blank"
        if not self.license_number.strip():
            return False, "license_number is empty/blank"
        if not self.npi.strip():
            return False, "npi is empty/blank"
        if not self.reviewed:
            return False, "clinician did not attest review (reviewed=False)"
        if require_specialty_match and not self.same_or_similar_specialty:
            return False, (
                "same_or_similar_specialty not attested, but the deployer requires "
                "a same/similar-specialty reviewer for this medical-necessity denial"
            )
        return True, "ok"


class ClinicianOfRecordControl:
    """Enforces a clinician of record on medical-judgment denials."""

    def __init__(self, audit_chain: AuditChain | None = None) -> None:
        self._chain = audit_chain

    def attest_denial(
        self,
        *,
        case_ref: str,
        is_medical_necessity_denial: bool,
        clinician: ClinicianOfRecord | None,
        agent_id: str = "clinician-of-record-control",
        require_specialty_match: bool = False,
    ) -> None:
        """Record (and gate) a denial's clinician-of-record attestation.

        If ``is_medical_necessity_denial`` is True, a valid ``clinician`` is
        REQUIRED — absent or invalid, this raises
        ``ClinicianOfRecordMissingError`` and records a POLICY_VIOLATION so
        the refused denial is itself auditable.

        ``require_specialty_match`` (default False) lets a deployer in a state
        that mandates a same/similar-specialty reviewer ENFORCE that the
        clinician attested ``same_or_similar_specialty=True``. By default the
        field is recorded but not gated, since the requirement is state-specific.

        Non-medical-necessity denials (e.g. a benefit not covered by plan
        terms, eligibility) do not require a clinician of record; they are
        still recorded for completeness.
        """
        if is_medical_necessity_denial:
            # Evaluate the attestation once and reuse the (ok, reason) pair so
            # the two branches cannot diverge.
            ok, reason = (
                (False, "no clinician supplied")
                if clinician is None
                else clinician.is_valid(require_specialty_match=require_specialty_match)
            )
            if not ok:
                if self._chain is not None:
                    self._chain.append(
                        event_type=AuditEventType.POLICY_VIOLATION,
                        autonomy_level=AutonomyLevel.A2,
                        agent_id=agent_id,
                        payload={
                            "control": "clinician_of_record",
                            "case_ref": case_ref,
                            "violation": "medical_necessity_denial_without_clinician_of_record",
                            "reason": reason,
                        },
                    )
                raise ClinicianOfRecordMissingError(
                    f"medical-necessity denial for case {case_ref!r} requires a "
                    f"valid clinician of record: {reason}"
                )

        if self._chain is not None:
            payload = {
                "case_ref": case_ref,
                "is_medical_necessity_denial": is_medical_necessity_denial,
            }
            if clinician is not None:
                payload.update(
                    {
                        "clinician_name": clinician.clinician_name,
                        "license_number": clinician.license_number,
                        "npi": clinician.npi,
                        "reviewed": clinician.reviewed,
                        "same_or_similar_specialty": clinician.same_or_similar_specialty,
                    }
                )
            self._chain.append(
                event_type=AuditEventType.CLINICIAN_OF_RECORD_ATTESTED,
                autonomy_level=AutonomyLevel.A2,
                agent_id=agent_id,
                payload=payload,
            )
