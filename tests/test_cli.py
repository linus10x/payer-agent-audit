"""CLI tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from payer_agent_audit.cli import main
from payer_agent_audit.governance.audit_chain import AuditChain
from payer_agent_audit.schemas.audit_event import AuditEventType, AutonomyLevel


def test_cli_info(capsys):
    assert main(["info"]) == 0
    out = capsys.readouterr().out
    assert "payer-agent-audit" in out
    assert "P3 AuditChain" in out


def test_cli_obligations(capsys):
    rc = main(["obligations", "--funding", "medicare_advantage", "--category", "expedited_urgent"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "CMS" in out
    assert "3 days, 0:00:00" in out  # 72h renders as "3 days, 0:00:00"
    assert "CMS-0057-F" in out


def test_cli_obligations_self_funded(capsys):
    main(["obligations", "--funding", "self_funded_erisa", "--category", "standard_preservice"])
    out = capsys.readouterr().out
    assert "DOL (EBSA)" in out
    assert "2560.503-1" in out


def test_cli_verify_ok(tmp_path: Path, capsys):
    log = tmp_path / "c.jsonl"
    chain = AuditChain(log_file=log, deployer_id="acme-health-prod")
    chain.append(
        event_type=AuditEventType.PRIOR_AUTH_DECISION,
        autonomy_level=AutonomyLevel.A2,
        agent_id="um",
        payload={"d": "approved"},
    )
    assert main(["verify", "--jsonl", str(log)]) == 0
    assert "OK: chain verified" in capsys.readouterr().out


def test_cli_verify_missing_file(tmp_path: Path):
    assert main(["verify", "--jsonl", str(tmp_path / "nope.jsonl")]) == 2


def test_cli_verify_tamper(tmp_path: Path):
    import json

    log = tmp_path / "c.jsonl"
    chain = AuditChain(log_file=log, deployer_id="acme-health-prod")
    chain.append(
        event_type=AuditEventType.PRIOR_AUTH_DECISION,
        autonomy_level=AutonomyLevel.A2,
        agent_id="um",
        payload={"d": "denied"},
    )
    lines = log.read_text().splitlines()
    rec = json.loads(lines[-1])
    rec["payload"] = {"d": "approved"}
    lines[-1] = json.dumps(rec, sort_keys=True)
    log.write_text("\n".join(lines) + "\n")
    assert main(["verify", "--jsonl", str(log)]) == 1


def test_cli_no_command_errors():
    with pytest.raises(SystemExit):
        main([])
