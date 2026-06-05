# FAILURE-MODES.md

**Status:** v0.1.0 · Last reviewed: 2026-06-05

> **Patterns are software, not legal advice.** Regulatory citations below are reference mappings; consult counsel for applicability.

## How to read this document

Rows 1–4 are **within the trust boundary** and addressable by the shipped controls today. Rows 5–8 cross the trust boundary and are deployer responsibilities by design. The framework is **fail-closed for verify-side checks** (production mode refuses to start without its required controls) and best-effort with explicit fallback for advisory-mode defaults. When in doubt, the audit chain prefers a missing operation over a missing audit record.

## Matrix

| # | Class | Example | Detection | Recovery | Reg mapping |
|---|---|---|---|---|---|
| 1 | In-place ledger tamper | A stored event's payload is edited after writing | `AuditChain.verify_strict` + `AuditEvent.from_jsonl` recompute on load | Re-derive from witness anchor / backup | NAIC AI governance; SOC 2 CC7.2 (analog) |
| 2 | Agent self-clears its veto | Vetoed agent calls `clear(operator_id=agent_id)` | Unconditional self-clear guard (`VetoBlockedError`) | Authenticated human operator clears | Human-oversight principle |
| 3 | Illegal autonomy resumption | One-call `HALT → NORMAL` after an incident | DEFCON transition-direction guard | Stepwise, re-authorized de-escalation | Graduated-autonomy governance |
| 4 | Model self-challenge | Same callable as primary and challenger | `ChallengerNotIndependentError` in code | Wire a genuinely independent challenger | SR 11-7 effective-challenge analog |
| 5 | End-to-end chain regeneration | Attacker with write access rebuilds the whole chain | **Across boundary** — external witness anchor only (non-optional in production mode) | Witness-register inclusion proof | NAIC; recordkeeping integrity |
| 6 | Forged operator identity | A spoofed `operator_id` clears a veto | **Across boundary** — strength of the deployer's `Authorizer` (IdP/KMS/mTLS) | Deployer IdP revocation | Access-control (deployer) |
| 7 | False independence attestation | Operator attests a same-family challenger as independent | **Across boundary** — attested, not code-detected | Second-line model-risk review | SR 11-7 analog (deployer) |
| 8 | Wrong funding-type routing input | A plan mislabeled as fully-insured when ERISA self-funded | **Across boundary** — input correctness is the deployer's | Deployer plan-data validation | ERISA / CMS / state DOI |

## Defaults

| Posture | Default behavior |
|---|---|
| Construction without `production=True` | Advisory mode; warns; not enforcing |
| `production=True` without required controls | Fails closed (refuses to construct) |
| Veto state store | In-memory (advisory); durable store is deployer-wired |
| Witness register | None by default; mandatory in production mode |
| State-DOI timeframe | Not asserted unless deployer supplies a primary-source value |

## What this document is NOT

- **Not exhaustive.** Threat surfaces outside these classes are deployer responsibilities by design.
- **Not a penetration test.** It is a design-level failure matrix.
- **Not a clinical safety analysis.** This framework makes no clinical determination.

## Related

- [LIMITATIONS.md](LIMITATIONS.md) · [DISCLAIMER.md](DISCLAIMER.md) · [NEGATIVE-USE-CASES.md](NEGATIVE-USE-CASES.md)

*Patterns are software, not legal advice.*
