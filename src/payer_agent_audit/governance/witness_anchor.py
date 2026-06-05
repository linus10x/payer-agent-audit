"""External witness anchoring for the audit chain — ADR-0014 analog.

The audit chain (``audit_chain.py``) is an *internally consistent*
hash-chain: SHA-256 prev-hash links make in-place tampering detectable
within the trust boundary that produced the chain. It is NOT
adversarially tamper-evident on its own — an attacker with full write
access to the storage layer can regenerate the entire chain end-to-end,
and the regenerated chain passes ``verify()``.

To make end-to-end regeneration *detectable*, the chain head must be
periodically anchored to an **external witness register** the deployer
does not control alone: OpenTimestamps, Sigstore Rekor, a regulator-side
append-only log, or a notarized blockchain anchor. This module defines
the ``WitnessRegister`` Protocol plus a small in-process witness used in
tests and a reference ``RekorWitness`` shape for deployers to wire.

This is the control that ``AuditChain(production=True)`` requires to be
present — see the production-mode fail-closed checks in ``audit_chain.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from payer_agent_audit.governance.audit_chain import AuditChain
    from payer_agent_audit.schemas.audit_event import AuditEvent


@dataclass(frozen=True)
class WitnessReceipt:
    """Receipt returned by a witness register for an anchored chain head.

    ``register_name`` / ``register_url`` identify the external witness.
    ``submitted_at`` is the deployer-side submission time. ``receipt_id``
    is the witness-side handle (Rekor inclusion UUID, OTS calendar
    reference, etc.) a verifier uses to independently confirm the anchor.
    """

    register_name: str
    register_url: str
    chain_head_hex: str
    submitted_at: str
    receipt_id: str


@runtime_checkable
class WitnessRegister(Protocol):
    """An external append-only witness the deployer does not control alone."""

    def anchor(self, chain_head_hex: str) -> WitnessReceipt:
        """Submit ``chain_head_hex`` to the register and return a receipt."""
        ...  # pragma: no cover - Protocol method body


@dataclass
class InMemoryWitness:
    """Deterministic in-process witness for tests + local development.

    NOT a real external witness — it lives in the same process as the
    chain, so it provides NO adversarial guarantee. It exists so the
    production-mode wiring and ``anchor_to_witness`` flow are testable
    without a network. Deployers MUST substitute ``RekorWitness`` or an
    OpenTimestamps client in real deployments; that substitution is the
    deployer's responsibility (see LIMITATIONS.md).
    """

    register_name: str = "in-memory-witness"
    register_url: str = "memory://local"
    anchored: list[WitnessReceipt] = field(default_factory=list)

    def anchor(self, chain_head_hex: str) -> WitnessReceipt:
        receipt = WitnessReceipt(
            register_name=self.register_name,
            register_url=self.register_url,
            chain_head_hex=chain_head_hex,
            submitted_at=datetime.now(UTC).isoformat(),
            # Deterministic handle derived from the head — a real witness
            # returns its own inclusion id; here we echo the head so tests
            # can assert round-trip without a wall-clock-dependent value.
            receipt_id=f"mem:{chain_head_hex[:16]}",
        )
        self.anchored.append(receipt)
        return receipt


@dataclass(frozen=True)
class RekorWitness:
    """Reference shape for a Sigstore Rekor witness (deployer wires the client).

    This is a DOCUMENTED reference pattern, not an implemented network
    client — ``anchor`` raises ``NotImplementedError`` until a deployer
    supplies the Rekor submission. The shape is here so the production
    wiring type-checks and so the README/LIMITATIONS can point at a
    concrete substitution target. See https://docs.sigstore.dev/rekor.
    """

    rekor_url: str = "https://rekor.sigstore.dev"
    timeout_s: float = 10.0

    def anchor(self, chain_head_hex: str) -> WitnessReceipt:  # pragma: no cover
        raise NotImplementedError(
            "RekorWitness is a reference pattern. Wire the Sigstore Rekor "
            "client (rekor-cli or the REST API) and return a WitnessReceipt "
            "carrying the inclusion-proof UUID. This is a deployer "
            "responsibility — the base library ships zero network dependencies."
        )


def anchor_to_witness(
    *,
    audit_chain: AuditChain,
    witness: WitnessRegister,
    agent_id: str = "system:witness_anchor",
    actor_id: str | None = None,
) -> AuditEvent:
    """Anchor the chain head to ``witness`` and record the receipt in-chain.

    The receipt is written back as an ``AuditEventType.WITNESS_ANCHOR``
    event so the receipt is itself hash-chained: tampering with the
    receipt after the fact requires re-writing every entry that follows
    it, which the next external anchor would expose.
    """
    from payer_agent_audit.schemas.audit_event import AuditEventType, AutonomyLevel

    head = audit_chain.chain_head()
    receipt = witness.anchor(head)
    return audit_chain.append(
        event_type=AuditEventType.WITNESS_ANCHOR,
        autonomy_level=AutonomyLevel.A4,
        agent_id=agent_id,
        payload={
            "register_name": receipt.register_name,
            "register_url": receipt.register_url,
            "chain_head_hex": receipt.chain_head_hex,
            "submitted_at": receipt.submitted_at,
            "receipt_id": receipt.receipt_id,
        },
        actor_id=actor_id,
    )
