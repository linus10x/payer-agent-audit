# NEGATIVE-USE-CASES.md

**Status:** v0.1.0 · Last reviewed: 2026-06-05

This document exists because an adopter under regulatory scrutiny will be asked, "what does this framework let you claim?" The list below is the deliberate enumeration of statements adopters and counsel should **not** make in reliance on this framework. Each entry names the false statement, marks it **FALSE**, and explains why.

> Read with [DISCLAIMER.md](DISCLAIMER.md) (legal) and [LIMITATIONS.md](LIMITATIONS.md) (bounded claims).

---

## Statements this framework does NOT support

### "This framework decides medical necessity." — FALSE.
It makes **no** medical-necessity or clinical determination. The clinician-of-record control records the **presence and attestation** of a licensed clinician's judgment on a medical-judgment denial; it does not evaluate the clinical merits. The judgment is the clinician's.

### "This framework is FDA-cleared / is a medical device." — FALSE.
A payer benefit adjudication is governed by insurance law, not the Federal Food, Drug, and Cosmetic Act. Nothing here is a medical device, and adopting it does not make a deployer's system one. See the payer-not-FDA-SaMD boundary in [LIMITATIONS.md](LIMITATIONS.md).

### "Adopting this framework satisfies our NAIC / state-DOI / ERISA / CMS obligations." — FALSE.
It provides recordkeeping and process-gating surfaces. The underlying obligations — timely determinations, full-and-fair review, appeal and external-review rights — remain the licensed insurer's, plan fiduciary's, or administrator's. The framework records what was done; it does not discharge the duty.

### "The audit chain proves the agent's decision was correct." — FALSE.
The hash chain proves the chain was not tampered with within its trust boundary. A chain of intact, correctly-hashed entries documenting a series of wrong decisions is still a chain of wrong decisions. The chain is evidence of what happened, not evidence that what happened was right.

### "The audit chain is tamper-proof." — FALSE.
It is tamper-**detecting** within the trust boundary, not tamper-proof. An attacker with full write access can regenerate the chain end-to-end; only an external witness anchor makes that detectable, and wiring a real witness is the deployer's responsibility.

### "The level-gate enforces our autonomy promotions." — FALSE.
The level-gate is advisory. It evaluates an attested evidence record against the criteria; it does not run the load test and does not validate the attester's identity end-to-end. Binding an attester to an authenticated principal is the deployer's identity-provider responsibility.

### "An independence attestation means the challenger model is provably independent." — FALSE.
Challenger-≠-primary is enforced in code, but vendor-family and prompt-template independence are **attested by the operator**, not detected by the harness. A false attestation is the operator's regulatory exposure.

### "This framework covers our P&C and Life/Annuity lines." — FALSE.
Only module (a) health-payer has shipped. P&C / Life-&-Annuity (module b) is on the roadmap and not built.

### "The state utilization-review timeframes are built in." — FALSE.
State-DOI timeframes vary by state and are not hardcoded. The framework refuses to assert a state-specific number it cannot cite and requires the deployer to supply it from the primary source.

---

## What this framework does support

See the affirmative claims in [LIMITATIONS.md](LIMITATIONS.md) ("What this framework DOES claim") and the [README](README.md).

## Related

- [DISCLAIMER.md](DISCLAIMER.md) · [LIMITATIONS.md](LIMITATIONS.md) · [FAILURE-MODES.md](FAILURE-MODES.md)

*Patterns are software, not legal advice.*
