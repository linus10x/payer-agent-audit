# LIMITATIONS.md — Bounded claims for payer-agent-audit v0.1.0

**Status:** v0.1.0 · Last reviewed: 2026-06-05

If a property is not stated as in-scope below, assume it is **out of scope** for this framework and the deployer's responsibility.

> This document is the bounded-claims layer. Read it with [DISCLAIMER.md](DISCLAIMER.md) (legal), [FAILURE-MODES.md](FAILURE-MODES.md) (adversarial matrix), and [NEGATIVE-USE-CASES.md](NEGATIVE-USE-CASES.md) (statements this framework does NOT support).

---

## The payer-not-FDA-SaMD boundary (read this first)

**This framework makes no medical-necessity or clinical determination, and nothing in it is a medical device.**

A health payer's coverage / utilization-management decision is **generally understood to be a benefit adjudication under insurance law** — governed by NAIC model guidance and state Departments of Insurance, ERISA (29 CFR 2560.503-1) for self-funded plans, CMS rules (CMS-0057-F) for Medicare Advantage and Medicaid managed care, and the ACA (45 CFR 147.136) for internal/external review — rather than by FDA Software-as-a-Medical-Device (SaMD) and clinical-decision-support regulation (the Federal Food, Drug, and Cosmetic Act as amended by §3060(a) of the 21st Century Cures Act, which excludes certain clinical-decision-support software from the device definition). **Whether any specific deployed system crosses into FDA-regulated clinical-decision-support is a fact-specific determination for the deployer's counsel — this observation is not legal advice and not a conclusion a deployer should rely on for its own system.** A system that surfaces treatment recommendations (not just coverage timeliness or benefit terms) may require an FDA analysis this framework does not perform.

Concretely:

- The controls in this framework govern **process and recordkeeping** — was a decision timely, did a denial that turned on medical judgment have an attested licensed clinician of record, were appeal and external-review rights afforded. They do **not** decide whether care is medically necessary.
- The clinician-of-record control records the **presence and attestation** of a clinician's judgment. The judgment itself belongs to the clinician.
- Nothing here is FDA-cleared, FDA-registered, or a medical device, and adopting it does not make a deployer's system one.

A test/doc scan (`tests/test_boundary_scan.py`) enforces that no control claims a medical-necessity or clinical determination.

---

## What this framework does NOT do

### Legal and regulatory

1. **This framework does not constitute legal or compliance advice.** The regulatory mappings below are reference mappings to help a deployer point qualified counsel at relevant clauses. Applicability is a deployer-and-counsel determination.
2. **This framework does not satisfy a deployer's NAIC, state-DOI, ERISA, CMS, or ACA obligations.** It provides a recordkeeping and process-gating surface; the underlying obligations remain the licensed insurer's, plan fiduciary's, or administrator's institutional responsibility.
3. **Reg timeframes are reference values, not legal certainty.** CMS-0057-F (72-hour expedited / 7-calendar-day standard) and ERISA 29 CFR 2560.503-1 (72-hour urgent / 15-day pre-service / 30-day post-service) timeframes are cited from their primary sources with a `verified` flag. State-DOI utilization-review timeframes vary by state and are **not** hardcoded — the framework refuses to assert a state-specific number it cannot cite, and requires the deployer to supply it. Confirm every timeframe against the primary source and counsel before relying on it operationally.
4. **MIT/Apache license does not shield a deployer from regulatory liability.** The license is a contract between author and adopter; it does not change the adopter's obligations to any regulator.

### Trust boundary and detection vs prevention

5. **The audit chain detects tampering; it does not prevent it.** The hash chain is internally consistent within the trust boundary that produced it. An attacker with full write access to the storage layer can regenerate the entire chain end-to-end, and the regenerated chain passes `verify()`. The chain is the evidence, not the enforcement mechanism.
6. **End-to-end regeneration is only detectable out-of-band.** That detection requires anchoring the chain head to an external witness register the deployer does not control alone (OpenTimestamps, Sigstore Rekor, a regulator-side log). `AuditChain(production=True)` refuses to start without that witness — but **wiring a real witness is the deployer's responsibility**; the shipped `InMemoryWitness` is for tests only and provides no adversarial guarantee.
7. **The level-gate is advisory.** It evaluates an attested evidence record against the promotion criteria. It does not run the load test, and it does not validate the attester's identity end-to-end — binding an attester to a real authenticated principal is the deployer's identity-provider responsibility. The gate is labeled advisory in code (`ADVISORY = True`) and here.

### Identity, persistence, infrastructure

8. **`operator_id` authentication is the deployer's Authorizer.** The sovereign veto and DEFCON machine bind `operator_id` to an authenticated principal only as strongly as the injected `Authorizer` does. In production mode an Authorizer is mandatory, but its strength (IdP / KMS / mTLS) is the deployer's wiring.
9. **Default persistence is in-memory.** The default veto state store loses state on restart. A production deployment must wire a durable `VetoStateStore`; this is documented, not implied.
10. **Independence of a challenger model is attested, not detected.** The effective-challenge harness rejects an identical primary/challenger callable and requires an operator independence attestation written to the chain. It cannot inspect a third-party vendor's model lineage to confirm that two differently-named models are not the same family or prompt template — that remains an operator attestation, and a false attestation is the operator's exposure.

### Coverage scope

11. **Module (a) health-payer ships first; module (b) P&C / Life-&-Annuity is not yet built.** Public claims must not imply P&C or Life/Annuity coverage until that module ships.
12. **Litigation references are matters of record only.** The golden corpus cites public dockets (filing court, case number, date) and the neutral allegation of record. It asserts no verdict, no characterization of merit, and no clinical or legal conclusion.

---

## What this framework DOES claim

- Five tested governance primitives built to a corrected specification: a level-gate requiring independent attestation, a sovereign veto that is un-self-clearable with a mandatory production Authorizer, a hash-chain ledger whose verifier branches the genesis seed (so both hardened and legacy chains verify) and whose production mode requires an external witness, a DEFCON state machine with a transition-direction guard, and an effective-challenge harness that enforces challenger ≠ primary and records attested independence.
- A funding-type-aware obligation map (CMS vs ERISA vs state DOI vs ACA) and three health-payer controls (UM timeliness, clinician-of-record-on-denial, appeal/IRO pathway), each wired to the audit chain.
- A test suite of unit, property-based (thousands of generated cases), golden-corpus, and mutation-tested coverage at ≥90%.
- Zero runtime dependencies.

These are **reference IP for adoption** — documented, tested patterns. The deployer's substrate is the production deployment.

---

## Related

- [DISCLAIMER.md](DISCLAIMER.md) — the legal contract and AS-IS terms
- [FAILURE-MODES.md](FAILURE-MODES.md) — the adversarial failure matrix
- [NEGATIVE-USE-CASES.md](NEGATIVE-USE-CASES.md) — statements this framework does not support

*Patterns are software, not legal advice.*
