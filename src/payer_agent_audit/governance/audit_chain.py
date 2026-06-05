"""Internally-Consistent Hash-Chained Audit Ledger (P3) — ADR-0003 analog.

Every governance event is appended to a chain where each entry contains
the SHA-256 hash of the previous entry. Modifying any past entry breaks
the SHA-256 link at that point and every entry after it — detectable by
an honest holder of the current chain head.

**Framing (read before relying on this).** This ledger is *internally
consistent* by construction (SHA-256 prev-hash links provide detection,
not prevention, within the trust boundary). It is **not adversarially
tamper-evident on its own**: an attacker with full write access to the
storage layer can regenerate the entire chain end-to-end, and the
regenerated chain passes ``verify()``. For adversarial integrity, the
chain head must be periodically anchored to an **external witness
register** the deployer does not control alone (OpenTimestamps, Sigstore
Rekor, a regulator-side log). See ``witness_anchor.py``.

P3 corrected-spec properties (the bar this is built to):
  * ``verify()`` / ``verify_strict()`` BRANCH the genesis prev-hash seed
    on whether a deployer-keyed genesis event #0 is present — seeding
    from ``_compute_genesis_hash(deployer_id, chain_creation_iso)`` when
    it is, and from the ``'0'*64`` legacy sentinel otherwise. BOTH a
    hardened chain and a legacy chain verify True.
  * In-place tamper is detected (per-line recompute on load + verify).
  * End-to-end regeneration is detectable ONLY via the external witness
    anchor, which is **non-optional in production mode**.

PRODUCTION MODE is a named strict opt-in (``production=True``). The
default constructor preserves the advisory, backward-compatible contract
and is labeled advisory in code + docs. Opting in FAILS CLOSED (refuses
to construct) without a deployer-keyed genesis AND a witness register.

The implementation is stdlib-only.
"""

from __future__ import annotations

import hashlib
import json
import sys
import threading
import uuid
import warnings
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if sys.platform != "win32":
    import fcntl
else:  # pragma: no cover - exercised on Windows hosts only
    fcntl = None  # type: ignore[assignment]

from payer_agent_audit.schemas.audit_event import (
    AuditEvent,
    AuditEventType,
    AutonomyLevel,
)

if TYPE_CHECKING:
    from payer_agent_audit.governance.witness_anchor import WitnessRegister

SCHEMA_VERSION = "1.0.0"
"""Default schema version stamped on events the chain constructs."""

GENESIS_HASH = "0" * 64
"""Legacy sentinel for the first entry's ``prev_hash``.

Retained for backward-compat detection of legacy (``deployer_id=None``)
chains and for callers that import the symbol. New chains use the
deployer-keyed derivation; loading a legacy chain emits a
``DeprecationWarning``. Do NOT remove this sentinel — the verifier
branches on it for legacy chains.
"""

GENESIS_DOMAIN_SEPARATOR = "payer-agent-audit/genesis/v1"
"""Domain-separation tag for ``_compute_genesis_hash``. Bumping the ``v1``
suffix is a chain-format break."""

GENESIS_AGENT_ID = "payer-audit-chain"
"""``agent_id`` carried on the genesis event #0, so verifiers can locate it
by name."""

GENESIS_VERSION = "v1"
"""Stamped on event #0 payload so verifiers can branch on format."""


def _compute_genesis_hash(deployer_id: str, chain_creation_iso: str) -> str:
    """Deployer-keyed seed for the genesis event's ``prev_hash``.

    Seed = ``SHA-256(domain_separator/deployer_id/chain_creation_iso)``.
    Two chains with different ``deployer_id`` (or ``chain_creation_iso``)
    produce different seeds — an attacker without the deployer's identity
    cannot regenerate a chain from scratch and match an existing
    deployer's head.
    """
    payload = f"{GENESIS_DOMAIN_SEPARATOR}/{deployer_id}/{chain_creation_iso}".encode()
    return hashlib.sha256(payload).hexdigest()


def _is_deployer_keyed_genesis(event: AuditEvent) -> bool:
    """True when ``event`` is a deployer-keyed genesis event #0."""
    return (
        event.agent_id == GENESIS_AGENT_ID
        and event.event_type == AuditEventType.AGENT_STARTED
        and isinstance(event.payload, dict)
        and event.payload.get("genesis_version") == GENESIS_VERSION
        and "deployer_id" in event.payload
        and "chain_creation_iso" in event.payload
    )


def _verify_seed_for_first(first_event: AuditEvent) -> str:
    """The ``prev_hash`` seed the chain's FIRST event must carry.

    Branches on whether event #0 is a deployer-keyed genesis event:

      * **Hardened chain** — re-derive the seed via
        ``_compute_genesis_hash`` from the genesis event's OWN payload,
        so a verifier that loaded the chain from disk (with no
        constructor ``deployer_id``) still validates it.
      * **Legacy chain** — the ``'0'*64`` sentinel.

    An attacker who rewrites the genesis ``deployer_id`` in place changes
    the expected seed but ALSO breaks the genesis event's own
    ``event_hash`` (the payload is folded into ``_compute_hash``), so
    in-place tamper is still caught. End-to-end regeneration is defended
    by the external witness anchor, NOT by this seed.
    """
    if _is_deployer_keyed_genesis(first_event):
        return _compute_genesis_hash(
            str(first_event.payload["deployer_id"]),
            str(first_event.payload["chain_creation_iso"]),
        )
    return GENESIS_HASH


class AuditChainTamperError(RuntimeError):
    """Raised by ``verify_strict`` when a mismatch is detected.

    Names the failing index and failure mode (event_hash mismatch vs
    prev_hash mismatch) so an investigation can pinpoint the corruption
    window.
    """


class AuditChain:
    """Append-only, hash-chained audit ledger (P3).

    Default (advisory) usage::

        chain = AuditChain(log_file=Path("audit.jsonl"))
        chain.append(event_type=AuditEventType.PRIOR_AUTH_DECISION,
                     autonomy_level=AutonomyLevel.A2, agent_id="um-agent",
                     payload={"decision": "approved"})
        assert chain.verify()

    Hardened usage (deployer-keyed genesis)::

        chain = AuditChain(deployer_id="acme-health-prod")

    Production usage (fail-closed — requires deployer_id + witness)::

        chain = AuditChain(deployer_id="acme-health-prod",
                           witness_register=RekorWitness(), production=True)
    """

    GENESIS_HASH = GENESIS_HASH

    def __init__(
        self,
        log_file: Path | None = None,
        witness_register: WitnessRegister | None = None,
        deployer_id: str | None = None,
        chain_creation_iso: str | None = None,
        production: bool = False,
        *,
        in_memory: bool = False,
    ) -> None:
        self._events: list[AuditEvent] = []
        self._witness_register = witness_register
        self._production = production

        # P3 PRODUCTION MODE — named strict opt-in. The default
        # (production=False) preserves the advisory contract exactly.
        # Opting in FAILS CLOSED (refuses to construct) unless the chain
        # is both deployer-keyed AND anchored to an external witness:
        # end-to-end regeneration is only DETECTABLE out-of-band, not by
        # the internally-consistent hash chain alone.
        if production:
            if deployer_id is None:
                raise ValueError(
                    "AuditChain(production=True) requires an explicit deployer_id "
                    "so event #0 is deployer-keyed; the legacy '0'*64 genesis "
                    "sentinel is advisory-only and cannot be used in production mode."
                )
            if witness_register is None:
                raise ValueError(
                    "AuditChain(production=True) requires a witness_register: the "
                    "hash chain is internally consistent but NOT adversarially "
                    "tamper-evident on its own. An external witness anchor "
                    "(OpenTimestamps / Rekor / regulator log) is the control that "
                    "makes end-to-end regeneration detectable. Refusing to start."
                )

        # RLock (not Lock) because ``anchor_to_witness`` re-enters
        # ``append`` while holding the lock.
        self._append_lock = threading.RLock()

        self._deployer_id = deployer_id
        if deployer_id is not None:
            self._chain_creation_iso: str | None = (
                chain_creation_iso or datetime.now(UTC).isoformat()
            )
        else:
            self._chain_creation_iso = chain_creation_iso

        # Persistence: JSONL file unless in_memory or no path.
        if in_memory:
            self.log_file: Path | None = None
        else:
            self.log_file = log_file or Path("output/audit_chain.jsonl")

        if self.log_file is not None:
            self._load_existing()

        # Seed genesis event #0 only when a deployer_id was explicitly
        # passed AND the chain is empty (so a re-opened chain keeps its
        # original genesis).
        if deployer_id is not None and len(self._events) == 0:
            self._seed_genesis_event()

    # ------------------------------------------------------------------ #
    # Genesis seeding                                                    #
    # ------------------------------------------------------------------ #

    def _seed_genesis_event(self) -> None:
        """Write a deterministic deployer-keyed event #0."""
        assert self._deployer_id is not None
        assert self._chain_creation_iso is not None
        deployer_id = self._deployer_id
        chain_creation_iso = self._chain_creation_iso

        seed = _compute_genesis_hash(deployer_id, chain_creation_iso)
        genesis_namespace = uuid.UUID("9c2e1b3d-2c9b-4a6e-8e3f-0b1f6a2c4b5d")
        event_id = str(
            uuid.uuid5(
                genesis_namespace,
                f"{GENESIS_DOMAIN_SEPARATOR}/{deployer_id}/{chain_creation_iso}",
            )
        )
        genesis_payload: dict[str, Any] = {
            "deployer_id": deployer_id,
            "chain_creation_iso": chain_creation_iso,
            "genesis_version": GENESIS_VERSION,
        }
        genesis_event = AuditEvent.create(
            event_type=AuditEventType.AGENT_STARTED,
            autonomy_level=AutonomyLevel.A0,
            agent_id=GENESIS_AGENT_ID,
            payload=genesis_payload,
            prev_hash=seed,
            event_id=event_id,
            timestamp=chain_creation_iso,
            schema_version=SCHEMA_VERSION,
        )
        self._events.append(genesis_event)
        if self.log_file is not None:
            self._write(genesis_event)

    # ------------------------------------------------------------------ #
    # Accessors                                                          #
    # ------------------------------------------------------------------ #

    @property
    def _prev_hash(self) -> str:
        """Current chain head; ``GENESIS_HASH`` for an empty chain."""
        if not self._events:
            return GENESIS_HASH
        return self._events[-1].event_hash

    def __len__(self) -> int:
        return len(self._events)

    # ------------------------------------------------------------------ #
    # Append + verify                                                    #
    # ------------------------------------------------------------------ #

    def append(
        self,
        event_type: AuditEventType,
        autonomy_level: AutonomyLevel,
        agent_id: str,
        payload: dict[str, Any],
        actor_id: str | None = None,
    ) -> AuditEvent:
        """Append a new event to the chain and persist it.

        Held under ``self._append_lock`` to close the TOCTOU window
        between reading the head and appending (two threads observing the
        same head would silently fork the chain).
        """
        with self._append_lock:
            prev_hash = self._prev_hash
            event = AuditEvent.create(
                event_type=event_type,
                autonomy_level=autonomy_level,
                agent_id=agent_id,
                payload=payload,
                prev_hash=prev_hash,
                actor_id=actor_id,
                schema_version=SCHEMA_VERSION,
            )
            self._events.append(event)
            if self.log_file is not None:
                self._write(event)
            return event

    def verify(self) -> bool:
        """Replay the chain and verify every hash. Returns False if tampered.

        The seed for event #0 BRANCHES on whether a deployer-keyed
        genesis event is present (hardened chain) or not (legacy chain),
        so BOTH verify True.
        """
        with self._append_lock:
            prev: str | None = None
            for event in self._events:
                if prev is None:
                    prev = _verify_seed_for_first(event)
                if event.event_hash != event._compute_hash():
                    return False
                if event.prev_hash != prev:
                    return False
                prev = event.event_hash
            return True

    def verify_strict(self) -> None:
        """Raise ``AuditChainTamperError`` on any inconsistency.

        Detects ``event_hash mismatch`` (entry changed after writing) and
        ``prev_hash mismatch`` (chain link broken). Same genesis-seed
        branching as ``verify``.
        """
        with self._append_lock:
            prev: str | None = None
            for index, event in enumerate(self._events):
                if prev is None:
                    prev = _verify_seed_for_first(event)
                if event.event_hash != event._compute_hash():
                    raise AuditChainTamperError(
                        f"event_hash mismatch at index {index} (event_id={event.event_id!r})"
                    )
                if event.prev_hash != prev:
                    raise AuditChainTamperError(
                        f"prev_hash mismatch at index {index} "
                        f"(event_id={event.event_id!r}): "
                        f"expected {prev!r}, got {event.prev_hash!r}"
                    )
                prev = event.event_hash

    def chain_head(self) -> str:
        """Return the chain head — the current ``event_hash`` of the last entry.

        Publish this periodically to an external witness register to convert
        the internally-consistent chain into an adversarially tamper-evident
        record. Returns the genesis sentinel for an empty chain.
        """
        return self._prev_hash

    def anchor_to_witness(self) -> AuditEvent | None:
        """Anchor the current chain head to the injected witness register.

        Writes the receipt back as a ``WITNESS_ANCHOR`` event so the
        receipt is itself hash-chained. Returns the receipt-bearing event,
        or ``None`` when no witness register is configured.
        """
        if self._witness_register is None:
            return None
        from payer_agent_audit.governance.witness_anchor import (
            anchor_to_witness as _anchor,
        )

        return _anchor(audit_chain=self, witness=self._witness_register)

    # ------------------------------------------------------------------ #
    # JSONL persistence                                                  #
    # ------------------------------------------------------------------ #

    def _write(self, event: AuditEvent) -> None:
        if self.log_file is None:
            return
        Path(self.log_file).parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_file, "a", encoding="utf-8") as fh:
            if fcntl is not None:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            try:
                fh.write(event.to_jsonl() + "\n")
                fh.flush()
            finally:
                if fcntl is not None:
                    fcntl.flock(fh.fileno(), fcntl.LOCK_UN)

    def _load_existing(self) -> None:
        if self.log_file is None:
            return
        p = Path(self.log_file)
        if not p.exists():
            return
        first_event_loaded: AuditEvent | None = None
        for line in p.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            data = json.loads(line)
            # Replay through ``from_jsonl`` so the recomputed hash is
            # checked against the stored hash at load time — a tampered
            # on-disk line raises before the event reaches the store.
            event = AuditEvent.from_jsonl(data)
            if first_event_loaded is None:
                first_event_loaded = event
            self._events.append(event)

        if first_event_loaded is not None and first_event_loaded.prev_hash == GENESIS_HASH:
            warnings.warn(
                f"AuditChain loaded from {str(p)!r} uses the legacy GENESIS_HASH "
                "sentinel (prev_hash='0'*64). Re-create this chain with an "
                "explicit deployer_id to engage the deployer-keyed genesis seed.",
                DeprecationWarning,
                stacklevel=3,
            )
