# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] — 2026-06-05

Initial release. Module (a) health-payer, under the NAIC umbrella.

### Added

- **Five corrected-spec primitives** (`governance/`):
  - Autonomy-ladder level-gate requiring independent attestation (rejects
    self-attestation, stale, and evidence-less claims); labeled advisory.
  - Sovereign veto — un-self-clearable; mandatory `Authorizer` in production
    mode; `operator_id` bound to an authenticated principal; documented durable
    state store.
  - Hash-chain audit ledger — verifier branches the genesis seed so both
    deployer-keyed hardened chains and legacy chains verify; production mode
    requires an external witness anchor; in-place tamper detected on load and
    on verify.
  - DEFCON state machine — immediate escalation, transition-direction guard on
    de-escalation (no one-call `HALT`/`SHUTDOWN → NORMAL`).
  - Effective-challenge harness — enforces challenger ≠ primary; records an
    operator independence attestation to the chain.
- **Module (a) health-payer controls** (`payer/`): funding-type obligation
  routing (CMS / ERISA / state DOI / ACA), UM-timeliness check,
  clinician-of-record-on-denial enforcement, appeal/IRO pathway control.
- **CLI** (`payer-audit`): `info`, `verify`, `obligations`.
- **Identity-guard hardening**: a shared NFKC + zero-width normalizer
  (`_normalize.py`) so the self-attestation (P1), self-clear (P2), and ERISA
  reviewer-independence guards cannot be defeated by Unicode-confusable or
  zero-width disguises of an id.
- **PEP 561**: ships a `py.typed` marker so adopters consume the strict types.
- **Audit-chain participation**: DEFCON transitions and the promotion gate now
  optionally emit to the audit chain, so every governance primitive can be
  ledgered.
- **Tests**: unit + contract, property-based (thousands of generated cases),
  golden corpus of public matters of record (primary-source URLs), the five
  AL-PROBES under `tests/adversarial/`, a payer-not-FDA-SaMD boundary scan, and
  a mutation pass (`scripts/mutation_check.py`). **100% line coverage, 100%
  mutation kill** (gate floor ≥90%).
- **Docs**: README, ARCHITECTURE (trust-boundary diagram), LIMITATIONS
  (payer-not-FDA-SaMD boundary), DISCLAIMER, FAILURE-MODES, NEGATIVE-USE-CASES,
  ASSURANCE-CATALOG, NOTICE, LICENSE, LICENSING, TRADEMARK, CITATION.cff, DOI-PLAN.

### Notes

- Reference IP for adoption — not a deployed control. Makes no
  medical-necessity or clinical determination.
- Module (b) P&C / Life-&-Annuity is on the roadmap and not yet shipped.
- Zero runtime dependencies.
