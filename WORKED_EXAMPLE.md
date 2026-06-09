# Worked example — the out-of-envelope case, end to end

This walks one prior-authorization decision the way a regulator would read it back: a decision class, an agent acting, the envelope catching the case that fell outside it, the audit entry, and the demotion that followed.

It governs the **record** of the decision. It **makes no medical-necessity or clinical determination** — that judgment belongs to the clinician. This library records whether a clinician was present and attested, whether the decision was timely under the rule that governs *this* plan, and what happened when the envelope was breached.

Run it:

```bash
python3 examples/worked_example.py
```

The runnable script is [`examples/worked_example.py`](examples/worked_example.py). It uses the real API — the same classes you import in production.

## The scenario

A health plan stands up an AI agent to help clear its prior-authorization queue. The decision class is **UM prior auth on a Medicare Advantage plan**, where CMS-0057-F sets a **72-hour clock** for an expedited/urgent request.

### 1–2. The decision class, and the agent acting on it

The agent reaches a determination on case `PA-12345` — a Medicare Advantage expedited prior-auth request received at hour 0, decided at **hour 80**.

```python
received = datetime(2026, 6, 1, 8, 0, tzinfo=UTC)
decided  = received + timedelta(hours=80)   # the agent decided at hour 80
```

### 3. The envelope catches the out-of-envelope case

A medical-necessity denial requires an **attested clinician of record** — the control refuses to let an agent issue that denial alone. This is presence and attestation, **not** a medical-necessity determination.

```python
ClinicianOfRecordControl(chain).attest_denial(
    case_ref="PA-12345",
    is_medical_necessity_denial=True,
    clinician=ClinicianOfRecord(
        clinician_name="Dr. A. Reviewer", license_number="TX-12345",
        npi="1234567890", reviewed=True, same_or_similar_specialty=True,
    ),
)
```

Then the timeliness control measures the decision against the rule the plan's funding type imposes. 80h > 72h → **BREACHED**:

```python
result = UMTimelinessControl(chain).check(
    funding_type=FundingType.MEDICARE_ADVANTAGE,
    category=RequestCategory.EXPEDITED_URGENT,
    request_received_at=received,
    decision_made_at=decided,
    case_ref="PA-12345",
)
assert result.met is False   # the breach is real, not the happy path
```

### 4. The audit entry

Every check above writes to the hash-chain ledger that detects tampering within its trust boundary. The record exists whether or not anyone is watching, and the chain is internally consistent by construction.

```python
assert chain.verify()
```

### 5. The demotion

The breach is an operational-risk signal — **not** a clinical determination. It escalates the agent's DEFCON autonomy state to `HALT`, and a sovereign veto engages so the agent cannot keep issuing this decision class until a human re-authorizes it.

```python
defcon.evaluate(RiskMetrics(breach_rate=0.35))          # -> DEFCON.HALT
veto.trigger(reason=VetoReason.UM_TIMELINESS_AT_RISK,
             triggered_by="compliance-monitor",
             description="PA-12345 decided at 80h vs the 72h CMS-0057-F floor")
assert veto.allow_execution() is False                  # halted pending human re-auth
```

## Actual output

Captured by running `python3 examples/worked_example.py`:

```
======================================================================
payer-agent-audit — worked example: the breach, end to end
======================================================================

[1-2] Decision class: Medicare Advantage expedited prior auth (PA-12345)
      received 2026-06-01T08:00:00+00:00  ->  decided 2026-06-04T16:00:00+00:00

[3] UM-timeliness envelope:
      deadline   = 3 days, 0:00:00  (CMS-0057-F (89 FR 8758) expedited prior-auth decision)
      elapsed    = 3 days, 8:00:00
      met        = False   <-- out of envelope (80h > 72h)

[4] Audit ledger:
      events recorded = 3
      chain verifies  = True
      chain head      = 7bcc7167ce837238...

[5] Demotion:
      DEFCON state   = HALT
      veto engaged   = True
      agent may run  = False   <-- halted pending human re-auth

----------------------------------------------------------------------
It governed the RECORD — timeliness, clinician presence, and the
demotion that followed the breach. It made NO medical-necessity or
clinical determination. That judgment stays with the clinician.
----------------------------------------------------------------------

final: chain verified=True, 4 events.
```

(The deadline prints as `3 days, 0:00:00` — that is 72 hours, the CMS-0057-F expedited clock. The chain head is a SHA-256 prefix and changes per run because event timestamps differ.)

## What this did, and what it did not

It governed the **record** — timeliness against the rule that governs this plan, the presence of an attested clinician, and the demotion that followed the breach.

It made **no medical-necessity or clinical determination.** Whether the requested care was appropriate is the clinician's judgment; this library only records whether that judgment was present, attested, timely, and appealable, and what the autonomy state did when an envelope was crossed.

For the framework behind A0→A4 and how each primitive maps to a rung, see [`AUTONOMY_LADDER.md`](AUTONOMY_LADDER.md) and [autonomy-ladder.io](https://autonomy-ladder.io).
