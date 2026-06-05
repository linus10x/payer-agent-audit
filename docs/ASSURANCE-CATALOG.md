# Assurance Catalog — payer-agent-audit v0.1.0

*MECE assurance catalog (JPMC-audit §4 protocol), scoped to this library. Each
row is labeled **implemented-control** (a tested control exists), **documented-
pattern** (a reference pattern, not an enforced control), or **deployer-owned**
(across the trust boundary). Real frameworks only; conditional rows marked.*

*Last reviewed: 2026-06-05. Generated against current HEAD, not a stale snapshot.*

---

## A. The five AL-PROBES (primitive adversarial probes — all PASS)

Committed as reproducible tests under `tests/adversarial/test_al_probes.py`. Each
re-authors the catalog's failing construction and asserts the corrected-spec
primitive REFUSES it.

| Probe | Primitive | Attack | Result | Evidence |
|---|---|---|---|---|
| AL-PROBE-01 | P1 level-gate | Promote A2→A3 with unmet lower controls / self-attestation | Refused | `test_al_probe_01*` |
| AL-PROBE-02 | P2 sovereign veto | Agent self-clears / unauthenticated operator clears | Refused (unconditional self-clear guard; production Authorizer mandatory) | `test_al_probe_02*` |
| AL-PROBE-03 | P3 audit chain | In-place tamper; hardened-chain false-tamper; e2e regeneration | Tamper detected; hardened AND legacy verify True; witness anchor in production | `test_al_probe_03*` |
| AL-PROBE-04 | P4 DEFCON | One-call `HALT`/`SHUTDOWN → NORMAL` | Refused (transition-direction guard); stepwise allowed | `test_al_probe_04*` |
| AL-PROBE-05 | P5 effective challenge | Self-challenge (challenger == primary) → clean accept | Rejected in code; independence attested to chain | `test_al_probe_05*` |

Run: `pytest tests/adversarial/test_al_probes.py` → all pass.

## B. Assurance domains (MECE)

| # | Domain (framework) | Control / artifact | Layer | Status |
|---|---|---|---|---|
| 1 | SDLC integrity | ruff + ruff-format + mypy --strict + pre-commit + SHA-pinned CI | CI | implemented-control |
| 2 | App/infra security | Bandit SAST · CodeQL · gitleaks · zero runtime deps | CI | implemented-control |
| 3 | Test assurance | unit + property (hypothesis, thousands of cases) + golden corpus + mutation (`scripts/mutation_check.py`) + boundary scan; cov ≥90% (actual 98%) | CI | implemented-control |
| 4 | Model-risk (SR 11-7 analog) | Effective-challenge harness: challenger ≠ primary enforced; independence attested to chain | Library | implemented-control (independence is attested, not detected) |
| 5 | Audit evidence (recordkeeping integrity) | Hash-chain ledger; genesis-branching verifier; in-place tamper detected on load + verify | Library | implemented-control (within trust boundary) |
| 6 | External tamper-evidence | Witness anchor (OpenTimestamps/Rekor) non-optional in production mode | Library | documented-pattern (`RekorWitness` is a reference shape; deployer wires the client) |
| 7 | Human oversight | Sovereign veto un-self-clearable; mandatory production Authorizer | Library | implemented-control (Authorizer strength is deployer-owned) |
| 8 | Graduated autonomy | DEFCON transition-direction guard; promotion level-gate with independent attestation | Library | implemented-control (level-gate labeled advisory) |
| 9 | Reg-specific obligations | Funding-type obligation map (CMS-0057-F · 42 CFR 438.210 · ERISA 2560.503-1 · ACA 147.136 · NAIC #073) | Library | implemented-control (state-DOI timeframes deployer-supplied; not asserted) |
| 10 | Payer-not-FDA-SaMD boundary | Boundary scan refuses any medical-necessity/clinical-determination claim | CI | implemented-control |
| 11 | Identity / persistence | `operator_id` authenticated principal; durable veto state store | Library | deployer-owned (IdP/KMS + durable store wired by deployer) |

## C. Where it fails first (and the remediation)

The adversarial pass (2026-06-05) surfaced these; all remediated and re-verified:

1. **Build hygiene** — a stale `.pyc` made 6 UM-timeliness tests red on a clean
   `pytest`. → Caches cleared; CI runs with `PYTHONDONTWRITEBYTECODE=1`; `__pycache__`
   gitignored.
2. **Medicaid timeframe** — Medicaid managed care was routed to CMS-0057-F's 7-day
   standard under a generic CMS citation. → Split to a dedicated 42 CFR 438.210(d)
   entry (verified against primary source): 72h expedited, 7-day standard on/after
   2026-01-01 (14-day before), distinct from MA.
3. **QHP-FFE flag** — `verified=True` with `deadline=None` was contradictory. →
   `verified=False` (no decision deadline exists to verify; the exclusion is sourced).
4. **Specialty match** — `same_or_similar_specialty` was recorded but not gateable.
   → `attest_denial(..., require_specialty_match=True)` enforces it where a state
   requires it.
5. **Dead code** — `_RejectAllAuthorizer` (unused, broken docstring) removed.

## D. Honesty discipline

No row implies a control that is not built. Items labeled documented-pattern or
deployer-owned are explicitly NOT enforced controls — see [LIMITATIONS.md](../LIMITATIONS.md)
and [FAILURE-MODES.md](../FAILURE-MODES.md). This library is reference IP for
adoption, not a deployed control, and makes no medical-necessity or clinical
determination.
