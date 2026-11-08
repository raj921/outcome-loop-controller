# Grade report — public_02_incidents

## Outcomes vs baseline (no-op controller)

| workflow | conclusion rate | Δ | pickup | Δ | engagement | Δ | engagement gap captured | hallucinated calls (base) |
|---|---|---|---|---|---|---|---|---|
| ks_cancel | 0.373 | +58.5% | 0.252 | +39.0% | 0.508 | +8.6% | 38% | 92 (348) |
| nw_kyc | 0.461 | +23.3% | 0.289 | +23.3% | 0.598 | -1.7% | 0% | 28 (29) |
| nw_renewal | 0.474 | +9.4% | 0.288 | +9.8% | 0.548 | -1.2% | 13% | 61 (54) |
| ALL | 0.425 | +28.6% | 0.272 | +23.7% | 0.541 | +1.6% | 25% | 181 (431) |

## Changes applied by the controller

30 applied — beneficial: 12, neutral: 18

- ks_cancel v2 (controller_approved) dims=['cohorts', 'welcome_message', 'voice', 'caller_id', 'schedule'] engageΔ=+0.013 didΔ=+0.007 → **beneficial**
- nw_renewal v2 (controller_approved) dims=['cohorts', 'welcome_message', 'voice', 'caller_id', 'schedule'] engageΔ=+0.026 didΔ=+0.015 → **beneficial**
- nw_kyc v2 (controller_approved) dims=['cohorts', 'caller_id', 'schedule'] engageΔ=+0.000 didΔ=+0.053 → **beneficial**
- ks_cancel v3 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.025 → **beneficial**
- nw_renewal v3 (controller_approved) dims=['welcome_message'] engageΔ=+0.034 didΔ=+0.000 → **beneficial**
- nw_kyc v3 (controller_approved) dims=['schedule'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- ks_cancel v4 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.181 → **beneficial**
- ks_cancel v5 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.141 → **beneficial**
- nw_renewal v4 (controller_approved) dims=['welcome_message', 'caller_id'] engageΔ=+0.087 didΔ=+0.056 → **beneficial**
- nw_kyc v4 (controller_approved) dims=['schedule'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- ks_cancel v7 (controller_approved) dims=['prompt_version'] engageΔ=+0.102 didΔ=+0.000 → **beneficial**
- ks_cancel v8 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.016 → **neutral**
- nw_renewal v5 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.011 → **neutral**
- nw_kyc v5 (controller_approved) dims=['schedule'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- nw_renewal v6 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=-0.003 → **neutral**
- ks_cancel v9 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=-0.000 → **neutral**
- nw_renewal v7 (controller_approved) dims=['welcome_message', 'caller_id'] engageΔ=+0.084 didΔ=+0.003 → **beneficial**
- nw_kyc v6 (controller_approved) dims=['caller_id', 'schedule'] engageΔ=+0.000 didΔ=+0.336 → **beneficial**
- nw_renewal v8 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.002 → **neutral**
- ks_cancel v10 (controller_auto) dims=['schedule'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- nw_kyc v7 (controller_approved) dims=['schedule'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- nw_renewal v10 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=-0.002 → **neutral**
- nw_kyc v8 (controller_approved) dims=['schedule'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- nw_renewal v11 (controller_auto) dims=['schedule'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- ks_cancel v11 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=-0.000 → **neutral**
- nw_kyc v9 (controller_approved) dims=['schedule'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- nw_renewal v12 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.008 → **neutral**
- ks_cancel v12 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.015 → **neutral**
- nw_kyc v10 (controller_approved) dims=['schedule'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- ks_cancel v13 (controller_approved) dims=['welcome_message', 'caller_id'] engageΔ=+0.017 didΔ=+0.019 → **beneficial**

## Governance

```
{
  "approval_requests": 18,
  "decisions": {
    "approved": 16,
    "rejected": 1,
    "expired": 0
  },
  "rejection_reasons": {
    "approver declined (judgement call)": 1
  },
  "applied_via_approval": 16,
  "auto_applied": 14,
  "auto_apply_rejected": 0,
  "apply_conflicts": 0,
  "lapsed": 0,
  "peak_requests_per_24h": {
    "nw_renewal": 1,
    "nw_kyc": 1,
    "ks_cancel": 2
  }
}
```

## Incidents

```
[
  {
    "type": "did_flagged",
    "workflow": "ks_cancel",
    "at": "D2 10:00",
    "flagged_did_share_by_day": {
      "2": 0.094,
      "3": 0.0,
      "4": 0.0,
      "5": 0.0,
      "6": 0.0,
      "7": 0.0,
      "8": 0.0,
      "9": 0.0
    }
  },
  {
    "type": "supervisor_edit",
    "workflow": "ks_cancel",
    "at": "D3 11:30",
    "mttr_minutes": 150,
    "fixed_by": "controller_approved"
  },
  {
    "type": "supervisor_edit",
    "workflow": "nw_renewal",
    "at": "D5 15:00"
  }
]
```

## Decaying variants — share of in-population calls still on the variant, by day after onset

```
{
  "nw_renewal:welcome_message=W3": {
    "2": 0.869,
    "3": 0.947,
    "4": 0.623,
    "5": 0.176,
    "6": 0.18,
    "7": 0.183,
    "8": 0.169,
    "9": 0.166
  }
}
```

Credits used: 3 · validation runs: 1 · LLM fix calls: 0