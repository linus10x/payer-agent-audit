# DOI plan — payer-agent-audit

*Status (2026-06-05): owner-authorized publication IN PROGRESS. Public repo +
v0.1.0 release are live; the DOI mint requires a one-time manual Zenodo↔GitHub
connection (OAuth, web UI) that cannot be automated.*

## Goal

Each Autonomy Ladder vertical library carries its own DOI so it can be cited
as a Day-1 backed vertical. This matches the sibling libraries' Zenodo flow.

## Steps

1. ✅ **Owner review** of the public prose (council 10/10) + reg-anchor staging
   (`S3c_insurance_regs_proposed.yaml`). Owner cleared 2026-06-05.
2. ✅ **Public remote created + pushed** — https://github.com/linus10x/payer-agent-audit
   (CI green: CI / CodeQL / Bandit / gitleaks all pass on `main`).
3. ✅ **Tag `v0.1.0` + GitHub Release** published —
   https://github.com/linus10x/payer-agent-audit/releases/tag/v0.1.0
4. ⏳ **Connect Zenodo (manual, owner — the one irreducible step):**
   zenodo.org → log in with GitHub → *Account → GitHub* → click **Sync now** →
   toggle **payer-agent-audit ON**. Then **re-publish the v0.1.0 release** so
   the Zenodo webhook fires (Zenodo only captures releases published *after* the
   toggle is on): `gh release delete v0.1.0 --yes && gh release create v0.1.0
   --verify-tag --title "v0.1.0 — health-payer governance (module a)"
   --notes-file <notes>`. Zenodo mints a version DOI + a resolving concept DOI.
5. ⏳ **Backfill** the `doi:` field in `CITATION.cff`, a DOI badge in the README,
   and a DOI badge bump — with the concept DOI.
6. ⏳ **Funnel flip — GATED ON THE DOI.** The funnel's backing copy
   (`_BACKING_COPY`) claims each vertical is "open, MIT-licensed, **Zenodo-archived**" —
   so Healthcare-Payer must not flip to `backed` until the DOI exists, or the copy
   overclaims. Exact change list in `00_Control/handoffs/S3c_payer_SHIPPED_note.md`
   (multi-file funnel-repo change, S2's lane: `CROSS_APPLIED_VERTICALS`,
   `VERTICAL_BACKING_LIBRARY`, `_BACKING_COPY`, `VERTICALS` ordering, and the
   funnel's `test_vertical_backing.py` sets).

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
