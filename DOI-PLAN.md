# DOI plan — payer-agent-audit

*Status: staged, NOT executed. Publishing to a public remote, tagging, and
minting a DOI are OWNER GATES — none performed without explicit owner sign-off.*

## Goal

Each Autonomy Ladder vertical library carries its own DOI so it can be cited
as a Day-1 backed vertical. This plan stages the payer-agent-audit DOI to match
the sibling libraries' Zenodo flow.

## Steps (owner-gated)

1. **Owner review** of the public prose (council 10/10 recorded) and the
   reg-anchor staging file (`S3c_insurance_regs_proposed.yaml`) after counsel
   review.
2. **Create public remote** `github.com/linus10x/payer-agent-audit` (owner).
3. **Connect Zenodo** to the repo (Zenodo GitHub webhook) so a Release mints a
   version DOI and a resolving concept DOI.
4. **Tag** `v0.1.0` and publish a GitHub Release. Zenodo mints the DOI.
5. **Backfill** the `doi:` field in `CITATION.cff` and the DOI badge in the
   README with the concept DOI.
6. **Funnel flip** — a later session actions the one-line `cross-applied →
   backed` flip for Healthcare-Payer per `S3c_payer_SHIPPED_note.md` (this
   library never edits the funnel directly).

## SemVer posture

- `0.1.0` — initial release, module (a) health-payer. Pre-1.0: the public API
  may change in minor versions until module (b) lands and the surface settles.
- A default/observable-contract change is a MAJOR bump; never re-tag a
  DOI'd version.

## Pre-release checklist

- [ ] `pytest --cov-fail-under=90` green (including AL-PROBES + boundary scan)
- [ ] `python3 scripts/mutation_check.py` meets the kill floor
- [ ] `ruff check` + `ruff format --check` + `mypy --strict` clean
- [ ] Council 10/10 recorded on README + CITATION (content + cosmetic + visual)
- [ ] Reg anchors primary-source-cited or marked UNVERIFIED; staging file filed
- [ ] No banned public-prose tokens (publish-check clean)
- [ ] Owner sign-off on the OWNER GATES above
