# Contributing

Thanks for your interest. This is reference governance IP; contributions
that strengthen the corrected-spec primitives, the health-payer controls,
the test suite, or the regulatory accuracy of the obligation map are welcome.

## Ground rules

- **Regulatory accuracy is a hard gate.** Any statute/CFR cite or timeframe
  must carry a primary-source URL or be marked `UNVERIFIED`. Never author a
  cite from memory.
- **No medical-necessity / clinical determination.** The library governs
  process and recordkeeping only — the boundary scan (`tests/test_boundary_scan.py`)
  enforces this.
- **Honest claim layer.** Label implemented-control vs documented-pattern;
  never imply a tested control that is not built.

## Local checks (all must pass)

```bash
pip install -e ".[dev,test-property]"
ruff check . && ruff format --check .
mypy --strict src/payer_agent_audit/ --ignore-missing-imports
pytest --cov=src/payer_agent_audit --cov-fail-under=90
python3 scripts/mutation_check.py
python3 scripts/banned_term_lint.py && python3 scripts/tamper_language_lint.py
python3 scripts/no_internal_notes_lint.py
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for the trust-boundary model and where the
five primitives + three controls sit relative to deployer-owned responsibilities.

## Versioning

Semantic Versioning. A default/observable-contract change is a MAJOR bump.
Never re-tag a DOI'd version.
