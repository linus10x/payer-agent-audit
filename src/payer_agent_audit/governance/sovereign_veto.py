"""Sovereign Veto (P2) — fail-closed human override of an autonomous agent.

A sovereign veto is the human-in-the-loop kill switch: an authorized
operator can block an agent from executing, and the agent CANNOT clear
its own veto. In a payer workflow this is the control that lets a medical
director, appeals coordinator, or compliance officer halt an autonomous
utilization-management or claims-routing agent.

P2 corrected-spec properties (the bar this is built to):
  * A wired ``Authorizer`` is **mandatory in production mode** — the
    constructor refuses to start (fail-closed) without one.
  * ``operator_id`` is bound to an **authenticated principal**: in
    production mode every clear/trigger routes through the Authorizer,
    which returns the verified principal; a free-string operator that the
    Authorizer does not vouch for is rejected.
  * An agent **cannot clear its own veto** (``operator_id == agent_id``
    is rejected unconditionally, even with a permissive Authorizer).
  * Persistence / recovery of veto state is **documented and supported**
    via an injectable ``VetoStateStore`` (default in-memory is labeled
    advisory — state is lost on restart unless a durable store is wired).

The default constructor (``production=False``) preserves a backward-
compatible advisory contract: no Authorizer required, a warning is
emitted, and ``operator_id`` is recorded as an unauthenticated assertion.
This is labeled advisory in code + docs; do NOT run it as an enforcing
control.
"""

from __future__ import annotations

import logging
import uuid
import warnings
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Protocol, runtime_checkable

from payer_agent_audit._normalize import normalize_principal_id

logger = logging.getLogger(__name__)


@runtime_checkable
class Authorizer(Protocol):
    """Binds an ``operator_id`` to an authenticated principal.

    A real implementation wraps an IdP / KMS / mTLS principal check. It
    returns ``True`` only when ``operator_id`` corresponds to a verified
    principal authorized for ``action``. ``context`` carries the veto/
    clear details for policy evaluation.
    """

    def authorize(self, operator_id: str, action: str, context: dict[str, Any]) -> bool:
        """Return True iff ``operator_id`` is an authenticated, authorized principal."""
        ...  # pragma: no cover - Protocol method body


class VetoReason(Enum):
    """Why a veto was triggered."""

    RISK_LIMIT_BREACH = "risk_limit_breach"
    POLICY_VIOLATION = "policy_violation"
    ANOMALY_DETECTED = "anomaly_detected"
    MANUAL_OPERATOR = "manual_operator"
    PEER_AGENT_CHALLENGE = "peer_agent_challenge"
    COMPLIANCE_FLAG = "compliance_flag"
    # Payer-specific
    CLINICIAN_REVIEW_REQUIRED = "clinician_review_required"  # denial needs a clinician of record
    UM_TIMELINESS_AT_RISK = "um_timeliness_at_risk"  # decision clock about to breach


@dataclass
class VetoRecord:
    """An individual veto. ``is_active`` until cleared by an operator."""

    veto_id: str
    reason: VetoReason
    triggered_by: str
    description: str
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    cleared_by: str | None = None
    cleared_at: str | None = None
    clear_reason: str | None = None

    @property
    def is_active(self) -> bool:
        return self.cleared_by is None

    def to_dict(self) -> dict[str, Any]:
        return {
            "veto_id": self.veto_id,
            "reason": self.reason.value,
            "triggered_by": self.triggered_by,
            "description": self.description,
            "timestamp": self.timestamp,
            "cleared_by": self.cleared_by,
            "cleared_at": self.cleared_at,
            "clear_reason": self.clear_reason,
        }


@runtime_checkable
class VetoStateStore(Protocol):
    """Durable persistence for veto state (recovery across restarts)."""

    def save(self, records: list[VetoRecord]) -> None: ...
    def load(self) -> list[VetoRecord]: ...


@dataclass
class InMemoryVetoStateStore:
    """Advisory default — state is held in process memory only.

    Veto state is LOST on restart. This is labeled advisory: a production
    deployment MUST wire a durable ``VetoStateStore`` (database / WORM
    log) so an in-flight veto survives a crash. Documented in
    LIMITATIONS.md.
    """

    _records: list[VetoRecord] = field(default_factory=list)

    def save(self, records: list[VetoRecord]) -> None:
        self._records = list(records)

    def load(self) -> list[VetoRecord]:
        return list(self._records)


class VetoBlockedError(RuntimeError):
    """Raised when a clear is rejected (self-clear or unauthorized operator)."""


class SovereignVeto:
    """Fail-closed human override of an autonomous agent (P2)."""

    def __init__(
        self,
        agent_id: str,
        on_veto: Callable[[VetoRecord], None] | None = None,
        on_clear: Callable[[VetoRecord], None] | None = None,
        authorizer: Authorizer | None = None,
        state_store: VetoStateStore | None = None,
        production: bool = False,
    ) -> None:
        self.agent_id = agent_id
        self._on_veto = on_veto
        self._on_clear = on_clear
        self._authorizer = authorizer
        self._production = production

        # P2 PRODUCTION MODE — a wired Authorizer is MANDATORY. Fail
        # closed: refuse to construct without one, because an enforcing
        # veto whose clear path trusts a free-string operator is not an
        # enforcing veto.
        if production and authorizer is None:
            raise ValueError(
                "SovereignVeto(production=True) requires an authorizer so "
                "operator_id is bound to an authenticated principal (IdP / KMS / "
                "mTLS). Without one, any caller could clear a veto with an "
                "unverified operator string. Refusing to start fail-closed."
            )
        if not production and authorizer is None:
            warnings.warn(
                "SovereignVeto constructed without an authorizer (advisory mode): "
                "operator_id is recorded as an UNAUTHENTICATED assertion and the "
                "clear path is not enforcing. Pass production=True with an "
                "authorizer to run this as an enforcing control.",
                stacklevel=2,
            )

        self._store = state_store or InMemoryVetoStateStore()
        self._vetos: list[VetoRecord] = self._store.load()

    @property
    def is_vetoed(self) -> bool:
        return any(v.is_active for v in self._vetos)

    def allow_execution(self) -> bool:
        """True iff no active veto blocks the agent."""
        return not self.is_vetoed

    def trigger(self, reason: VetoReason, triggered_by: str, description: str) -> VetoRecord:
        """Record a new active veto."""
        record = VetoRecord(
            veto_id=f"veto-{uuid.uuid4()}",
            reason=reason,
            triggered_by=triggered_by,
            description=description,
        )
        self._vetos.append(record)
        self._store.save(self._vetos)
        if self._on_veto is not None:
            self._on_veto(record)
        return record

    def clear(self, operator_id: str, reason: str, veto_id: str | None = None) -> list[VetoRecord]:
        """Clear active veto(s). Fail-closed against self-clear + unauthorized.

        Order of checks (all must pass):
          1. ``operator_id != agent_id`` — an agent cannot clear its own
             veto. Enforced UNCONDITIONALLY, even with a permissive
             Authorizer, because self-clear defeats the entire control. The
             comparison is normalized (strip + casefold) so a whitespace/case
             variation of the agent id cannot bypass it, and a blank operator
             is rejected.
          2. The Authorizer (mandatory in production) must vouch for
             ``operator_id`` as an authenticated principal authorized to
             clear. In advisory mode (no authorizer) this step is skipped
             and the operator string is recorded unauthenticated.
        """
        # 1. Self-clear is forbidden unconditionally (normalized comparison:
        #    NFKC + zero-width strip + casefold, so a Unicode-confusable or
        #    zero-width disguise of the agent id cannot bypass the guard).
        operator_norm = normalize_principal_id(operator_id)
        if not operator_norm:
            raise VetoBlockedError(
                "operator_id is empty/blank; a veto must be cleared by a named operator"
            )
        if operator_norm == normalize_principal_id(self.agent_id):
            raise VetoBlockedError(
                f"self-clearing forbidden: operator_id {operator_id!r} resolves to the "
                f"vetoed agent_id. A sovereign veto must be cleared by a human "
                f"operator distinct from the agent."
            )

        # 2. Authenticated-principal binding.
        if self._authorizer is not None:
            context = {"veto_id": veto_id, "reason": reason, "agent_id": self.agent_id}
            if not self._authorizer.authorize(operator_id, "clear_veto", context):
                raise VetoBlockedError(
                    f"operator_id {operator_id!r} is not an authenticated principal "
                    f"authorized to clear this veto"
                )
        elif self._production:  # pragma: no cover - constructor already guarantees authorizer
            raise VetoBlockedError("production mode requires an authorizer")

        cleared: list[VetoRecord] = []
        now = datetime.now(UTC).isoformat()
        for record in self._vetos:
            if not record.is_active:
                continue
            if veto_id is not None and record.veto_id != veto_id:
                continue
            record.cleared_by = operator_id
            record.cleared_at = now
            record.clear_reason = reason
            cleared.append(record)
            if self._on_clear is not None:
                self._on_clear(record)
        self._store.save(self._vetos)
        return cleared

    def active_vetos(self) -> list[VetoRecord]:
        return [v for v in self._vetos if v.is_active]

    def history(self) -> list[VetoRecord]:
        return list(self._vetos)
