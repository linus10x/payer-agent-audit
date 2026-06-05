# payer-agent-audit — internal build research notes (NOT published)

*Compiled 2026-06-05 from primary-source research. VERIFIED = primary/authoritative text fetched. FLAGGED = needs counsel/fresh-read before any PUBLIC assertion. Matters-of-record only.*

## Verified reg anchors (module a — health-payer)

### NAIC Model Bulletin — Use of AI Systems by Insurers
- Title: *Model Bulletin: Use of Artificial Intelligence Systems by Insurers*; adopted **2023-12-04** by full NAIC membership.
- State adoption: SSOT `naic_model_ai_bulletin` carries `state_adoption_count: 24` (verified 2026-06-03). Cite THAT value + date. Independent confirm: "24 states as of March 2025" (Quarles, citing NAIC tracker). Exact 2026 count = FLAGGED (NAIC tracker PDF unparseable by fetch) — cite "at least 24 (verified 2026-06-03 per reg SSOT)".
- URL: https://content.naic.org/insurance-topics/artificial-intelligence

### CMS-0057-F — Interoperability and Prior Authorization Final Rule
- FR publication: **2024-02-08, 89 FR 8758** (FR doc 2024-00895). CMS public release 2024-01-17.
- Affected payers: MA orgs; Medicaid FFS (state agencies); Medicaid managed care; CHIP FFS; CHIP managed care; QHP issuers on FFEs.
- PA decision timeframes: **expedited/urgent = 72 hours; standard = 7 calendar days** (QHP-FFE issuers excluded from the timeframe req); specific denial reason required.
- Compliance dates: decision-timeframe + denial-reason **effective 2026-01-01**; API requirements (Prior Auth/Patient Access/Provider Access/Payer-to-Payer) **generally 2027-01-01**; PA metrics first public posting by 2026-03-31.
- URL: https://www.cms.gov/newsroom/fact-sheets/cms-interoperability-prior-authorization-final-rule-cms-0057-f
- FLAG: FR page (89 FR 8758) not directly fetched (anti-bot 403); timeframes consistent across CMS-sourced reporting. Counsel eyeball recommended before publish.

### ERISA claims-procedure — 29 CFR 2560.503-1 (DOL EBSA) — VERIFIED (Cornell LII)
- Group health initial: urgent **72h** [(f)(2)(i)]; pre-service non-urgent **15 days** (+15 ext) [(f)(2)(iii)(A)]; post-service **30 days** (+15 ext) [(f)(2)(iii)(B)].
- Appeals [(i)]: urgent **72h**; pre-service **30 days**; post-service **60 days**.
- Full-and-fair-review (h): reviewer not the original decision-maker, no deference to initial denial, health-care-professional consultation for medical-judgment claims.
- Governs self-funded ERISA group health plans. URL: https://www.ecfr.gov/current/title-29/subtitle-B/chapter-XXV/subchapter-G/part-2560/section-2560.503-1 (text via https://www.law.cornell.edu/cfr/text/29/2560.503-1)

### State DOI / utilization review
- NAIC Utilization Review and Benefit Determination Model Act (Model #073 / I-73) + Health Carrier Grievance Procedure Model Act + Uniform Health Carrier External Review Model Act. Governs fully-insured plans. URL: https://content.naic.org/sites/default/files/model-law-073.pdf
- Hard state statutes (CA H&S §1367.01 Knox-Keene; TX Ins. Code Ch. 4201) — specific hour/day values NOT verified this pass → FLAGGED; do not quote a specific state timeframe without primary read.

### ACA internal/external review — 45 CFR 147.136 — VERIFIED (Cornell LII)
- Non-grandfathered plans: internal claims/appeals + external review. State external-review (NAIC Uniform Model Act standards) [(c)] or Federal process [(d)] → IRO (Independent Review Organization), random/rotational assignment, no conflicts of interest.
- URL: https://www.ecfr.gov/current/title-45/subtitle-A/subchapter-B/part-147/section-147.136 (text via https://www.law.cornell.edu/cfr/text/45/147.136)

## Litigation matters-of-record (golden corpus — matters of record ONLY)

### nH Predict — Estate of Gene B. Lokken v. UnitedHealth Group, Inc.
- Court: D. Minn. Case **0:23-cv-03514**. Filed **2023-11-14**.
- Matter of record: defendants used the **nH Predict** algorithm to determine MA post-acute-care coverage amounts, allegedly in lieu of physician judgment.
- Status (sourced, no characterization): 2025-02-13 Judge Tunheim allowed Counts 1 (breach of contract) & 2 (implied covenant) to proceed; dismissed Counts 3-7 with prejudice. Ongoing.
- URLs: https://www.courtlistener.com/docket/68006832/ · https://litigationtracker.law.georgetown.edu/litigation/estate-of-gene-b-lokken-the-et-al-v-unitedhealth-group-inc-et-al/

### Cigna PxDx — Kisting-Leung v. Cigna Corp.
- Court: E.D. Cal. Case **2:23-cv-01477**. Filed **2023-07-24**.
- Matter of record: Cigna's **PxDx** (procedure-to-diagnosis) system allegedly enabled bulk claim denials without individual file review (complaint references ~300k denials / 2 months 2022 at ~1.2s/claim, per ProPublica reporting cited therein).
- Status (sourced): 2025-03-31 E.D. Cal. allowed the action to proceed in relevant part. Ongoing.
- URLs: https://dockets.justia.com/docket/california/caedce/2:2023cv01477/431351 · https://www.courtlistener.com/docket/67631023/kisting-leung-v-cigna-corp/

## Payer-not-FDA-SaMD boundary — VERIFIED
A payer coverage/medical-necessity **benefit determination** is NOT an FDA-regulated medical device. FDA device authority runs from the FD&C Act, narrowed by **§3060(a) of the 21st Century Cures Act (2016-12-13)** amending FD&C §520 to exclude certain clinical-decision-support software [§520(o)(1)(E)]. FDA jurisdiction targets software informing clinical diagnosis/treatment of a patient by a clinician — not an insurer's payment/coverage decision. Payer determinations are reviewed via ERISA/ACA internal appeals + IRO external review, not FDA pathways.
- URL: https://www.fda.gov/regulatory-information/search-fda-guidance-documents/clinical-decision-support-software
- FLAG: FDA revised CDS guidance published 2026-01-06 supersedes Sept 2022; the §520(o)(1)(E) exclusion + payer-vs-device boundary unchanged. Cite generically.
