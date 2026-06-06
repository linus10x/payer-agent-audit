# payer-agent-audit

**The governance library that documents what it does *not* do — in code-enforced detail.** Detection, not prevention. Recordkeeping, not medical-necessity. Reference IP, not a deployed control. Most governance tooling oversells; this one ships its own failure matrix and an adversarial probe per primitive.

Governance patterns for autonomous AI agents in health-insurance / payer operations — utilization management, prior authorization, and claims/appeals — aligned to the NAIC Model Bulletin framework. This is **not** a deployed control operating in production, and it **makes no medical-necessity or clinical determination**: a payer coverage decision is a benefit adjudication under insurance law, distinct from FDA medical-device regulation. See [LIMITATIONS.md](LIMITATIONS.md).

![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue)
![License: MIT OR Apache-2.0](https://img.shields.io/badge/license-MIT%20OR%20Apache--2.0-green)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.20564377.svg)](https://doi.org/10.5281/zenodo.20564377)
![mypy: strict](https://img.shields.io/badge/mypy-strict-blue)
![ruff](https://img.shields.io/badge/lint-ruff-orange)
![coverage 100%](https://img.shields.io/badge/coverage-100%25-brightgreen)
![mutation 100%](https://img.shields.io/badge/mutation-100%25-brightgreen)
![Zero runtime deps](https://img.shields.io/badge/runtime%20deps-0-lightgrey)

---

## Table of Contents

- [Why this exists](#why-this-exists)
- [Quick start](#quick-start)
- [The five primitives](#the-five-primitives)
- [Module (a) — health-payer controls](#module-a--health-payer-controls)
- [Funding-type obligation routing](#funding-type-obligation-routing)
- [Threat model at a glance](#threat-model-at-a-glance)
- [Regulatory mapping](#regulatory-mapping)
- [What this is and is not](#what-this-is-and-is-not)
- [Testing](#testing)
- [Who this is for](#who-this-is-for)
- [Architecture](#architecture)
- [Author & disclosures](#author--disclosures)
- [License · Citation](#license--citation)

---

## Why this exists

Payers are putting autonomous and AI-assisted systems into utilization management, prior authorization, and claims adjudication support. The algorithmic-UM disputes now in litigation and on regulators' desks turn on the same question a regulator and a plaintiff both ask: *can you show, on the record, that a denial which turned on medical judgment had a licensed clinician of record, that the decision was timely under the rule that governs this plan, and that appeal rights were afforded?*

Where governance tooling typically ships a dashboard and a compliance checkbox, this ships a hash-chained evidence ledger, an adversarial probe per primitive, and a written list of the things it deliberately does not do.

This framework is the recordkeeping and process-gating answer to that question. It does not decide medical necessity. It refuses to let an autonomous agent issue a medical-judgment denial without an attested clinician of record, checks decision timeliness against the rule that the plan's funding type actually imposes, and writes every check to a hash-chained ledger. These are tested reference patterns — not academic proposals, and not a turnkey product.

## Quick start

```bash
pip install payer-agent-audit          # zero runtime dependencies
payer-audit info
payer-audit obligations --funding self_funded_erisa --category standard_preservice
```

```python
from payer_agent_audit.governance import AuditChain
from payer_agent_audit.payer import (
    UMTimelinessControl, FundingType, RequestCategory,
)
from datetime import datetime, timedelta, UTC

chain = AuditChain(deployer_id="acme-health-prod")          # hardened genesis
control = UMTimelinessControl(audit_chain=chain)

received = datetime(2026, 6, 1, 8, 0, tzinfo=UTC)
result = control.check(
    funding_type=FundingType.MEDICARE_ADVANTAGE,
    category=RequestCategory.EXPEDITED_URGENT,              # CMS-0057-F 72h
    request_received_at=received,
    decision_made_at=received + timedelta(hours=80),        # 80h > 72h
    case_ref="PA-12345",
)
assert result.met is False                                  # breach, recorded to the chain
assert chain.verify()
```

Runnable end-to-end: [`examples/quickstart_um_timeliness.py`](examples/quickstart_um_timeliness.py) — `python examples/quickstart_um_timeliness.py`.

## The five primitives

Built fresh to a corrected specification — each primitive ships with an adversarial probe (`tests/adversarial/`) that re-authors the exact failure mode an earlier-generation library admitted, and asserts this one refuses it. The defects are not described; they are tested against.

| Primitive | Module | What it does |
|---|---|---|
| **Autonomy-ladder level-gate** | `governance/autonomy_ladder.py` | Refuses A2→A3 promotion when lower-level controls are unmet; requires **independent attestation** of each input (rejects self-attestation, stale, or evidence-less claims). Labeled advisory. |
| **Sovereign veto** | `governance/sovereign_veto.py` | Human kill switch; an agent **cannot clear its own veto**; a wired `Authorizer` is **mandatory in production mode**; `operator_id` is bound to an authenticated principal; durable state store documented. |
| **Hash-chain ledger** | `governance/audit_chain.py` | Tamper-detecting (within-trust-boundary) append-only chain; the verifier **branches the genesis seed** so both a deployer-keyed hardened chain and a legacy chain verify; production mode requires an **external witness anchor**. |
| **DEFCON state machine** | `governance/defcon.py` | Graduated autonomy throttle; immediate escalation, hardened de-escalation — a **transition-direction guard** forbids a one-call `HALT`/`SHUTDOWN → NORMAL`. |
| **Effective-challenge harness** | `governance/effective_challenge_harness.py` | Independent model challenge; **enforces challenger ≠ primary** (a model cannot self-challenge to a clean accept); records an operator **independence attestation** to the chain. |

## Module (a) — health-payer controls

| Control | Module | Governs |
|---|---|---|
| **UM timeliness** | `payer/um_timeliness.py` | Was the decision made within the deadline the plan's funding type imposes (CMS-0057-F / ERISA / state DOI)? |
| **Clinician-of-record-on-denial** | `payer/clinician_of_record.py` | A medical-judgment denial requires an attested, licensed clinician who actually reviewed the case — refused otherwise, and the refusal is itself recorded. |
| **Appeal / IRO pathway** | `payer/appeal_iro.py` | Internal-appeal + IRO external-review rights afforded; ERISA full-and-fair-review independence (the appeal reviewer is not the original decision-maker). |

> Module (b) P&C / Life-&-Annuity is on the roadmap and **not yet shipped** — see [LIMITATIONS.md](LIMITATIONS.md). This README does not claim P&C or Life/Annuity coverage.

## Funding-type obligation routing

The same denial carries different obligations depending on who funds the plan. The obligation map routes each decision to the correct regime:

| Funding type | Primary regulator | UM-decision-timeliness anchor |
|---|---|---|
| Medicare Advantage | CMS | CMS-0057-F (72h expedited / 7-day standard, effective 2026-01-01) |
| Medicaid · CHIP managed care | CMS + State Medicaid | 42 CFR 438.210(d) (72h expedited / 7-day standard on/after 2026-01-01; 14d before) |
| Self-funded (ERISA) | DOL (EBSA) | 29 CFR 2560.503-1 (72h / 15d / 30d) |
| QHP on the FFE | HHS / CMS + state | No CMS-0057-F decision clock (QHP-FFE excluded); 45 CFR 147.136 governs appeals |
| Fully insured | State Department of Insurance | State UR statute (NAIC Model #073 framework) — deployer-supplied |

A deployer may **tighten** a verified deadline (a stricter internal SLA), never loosen one past the regulatory floor.

## Threat model at a glance

| Threat | In-boundary? | What stops it |
|---|---|---|
| Ledger edited after write | ✅ shipped control | Recompute-on-load + `verify_strict` |
| Agent clears its own veto (incl. case / Unicode-confusable disguise) | ✅ shipped control | Unconditional, normalized self-clear guard |
| One-call `HALT`/`SHUTDOWN → NORMAL` | ✅ shipped control | Transition-direction guard (stepwise + re-authorized) |
| Whole chain regenerated by an attacker with write access | ❌ across boundary | **Only** an external witness anchor — your wiring |
| Operator falsely attests an independent challenger | ❌ across boundary | Second-line model-risk review — your process |

Shipped-and-tested controls draw the trust boundary; the across-boundary rows are handed back to the deployer, explicitly, by design. Full 8-row matrix with regulatory mappings: [FAILURE-MODES.md](FAILURE-MODES.md).

## Regulatory mapping

Reference mappings to help a deployer point qualified counsel at relevant clauses; applicability is a deployer-and-counsel determination. Primary sources, with a `verified` flag in code:

- **NAIC Model Bulletin: Use of AI Systems by Insurers** (adopted 2023-12-04; at least 24 states adopted, per the reg source verified 2026-06-03)
- **CMS-0057-F** Interoperability and Prior Authorization Final Rule (89 FR 8758, 2024-02-08; RIN 0938-AU87; decision timeframes effective 2026-01-01)
- **Medicaid / CHIP managed care** 42 CFR 438.210(d) (service-authorization timeframes; standard tightened to 7 days on/after 2026-01-01 by CMS-0057-F)
- **ERISA claims-procedure** 29 CFR 2560.503-1 (DOL EBSA)
- **ACA internal/external review** 45 CFR 147.136 (IRO pathway)
- **State utilization review** — NAIC Utilization Review and Benefit Determination Model Act (#073)

## What this is and is not

- It **is** reference IP for adoption: documented, tested governance patterns with zero runtime dependencies.
- It **is not** a deployed control, a medical device, FDA-cleared software, legal advice, or a guarantee of any regulatory outcome.
- It **makes no medical-necessity or clinical determination.** The clinician's judgment belongs to the clinician; this framework governs whether that judgment is present, attested, timely, and appealable.

The framework is the governed pattern; the production deployment is the deployer's substrate underneath it. This repo gives you the first and refuses to pretend it gives you the second.

## Testing

```bash
pip install -e ".[dev,test-property]"
pytest --cov=src/payer_agent_audit --cov-fail-under=90      # unit + property + golden + boundary
python3 scripts/mutation_check.py                            # mutation pass (kill score)
```

The suite includes unit + contract tests, property-based tests (thousands of generated cases per primitive), a golden corpus of public matters of record (each with a primary-source URL), the five AL-PROBES under `tests/adversarial/`, and a payer-not-FDA-SaMD boundary scan. The gate is **≥90%**; the suite currently runs at **100% line coverage with a 100% mutation kill** — coverage is a floor, not a finish line (see [docs/ASSURANCE-CATALOG.md](docs/ASSURANCE-CATALOG.md)).

## Who this is for

Health-plan model-risk, compliance, and engineering teams putting autonomy into UM/PA/claims workflows who need an auditable governance substrate a regulator can read and they can adapt — and the diligence teams who have to assess one.

**Not for you if** you want a turnkey UM engine, a medical-necessity classifier, or a control you can deploy without wiring your own identity provider, durable store, and external witness. This is a substrate to adapt, not a product to install.

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for the trust-boundary diagram — the five primitives and three controls inside the boundary, and the four responsibilities (Authorizer/IdP, durable store, external witness, deployer process) explicitly outside it.

## Author & disclosures

Authored by Kunjar Bhaduri through North Texas Capital Investments, an independent research effort. This is independent research; it is not produced on behalf of, and does not represent the views of, any employer or client, and contains no employer- or client-confidential material. The regulatory content is reference mapping, not legal advice — see [DISCLAIMER.md](DISCLAIMER.md).

## License · Citation

Dual-licensed **MIT OR Apache-2.0**. If you use this framework in research or production, please cite it — see [CITATION.cff](CITATION.cff). Trademark posture: [docs/TRADEMARK.md](docs/TRADEMARK.md).

*Patterns are software, not legal advice.*
