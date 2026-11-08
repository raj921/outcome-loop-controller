# Grade report — public_01_dev

## Outcomes vs baseline (no-op controller)

| workflow | conclusion rate | Δ | pickup | Δ | engagement | Δ | engagement gap captured | hallucinated calls (base) |
|---|---|---|---|---|---|---|---|---|
| ks_cancel | 0.389 | +13.8% | 0.263 | +7.7% | 0.508 | +3.3% | 23% | 66 (57) |
| nw_kyc | 0.443 | +20.8% | 0.291 | +20.4% | 0.594 | -0.6% | 0% | 26 (21) |
| nw_renewal | 0.474 | +13.8% | 0.285 | +7.8% | 0.564 | +4.1% | 19% | 44 (54) |
| ALL | 0.429 | +15.3% | 0.276 | +10.1% | 0.545 | +3.0% | 16% | 136 (132) |

## Changes applied by the controller

24 applied — neutral: 14, beneficial: 10

- ks_cancel v2 (controller_approved) dims=['cohorts', 'welcome_message', 'voice', 'caller_id', 'schedule'] engageΔ=-0.003 didΔ=+0.007 → **neutral**
- nw_renewal v2 (controller_approved) dims=['cohorts', 'welcome_message', 'voice', 'caller_id', 'schedule'] engageΔ=+0.041 didΔ=-0.011 → **beneficial**
- nw_kyc v2 (controller_approved) dims=['cohorts', 'caller_id', 'schedule'] engageΔ=+0.000 didΔ=+0.053 → **beneficial**
- nw_renewal v3 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.037 → **beneficial**
- ks_cancel v3 (controller_approved) dims=['welcome_message'] engageΔ=+0.019 didΔ=+0.000 → **beneficial**
- nw_renewal v4 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.034 → **beneficial**
- ks_cancel v4 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.025 → **beneficial**
- nw_kyc v3 (controller_approved) dims=['schedule'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- nw_renewal v5 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.010 → **neutral**
- ks_cancel v5 (controller_approved) dims=['voice', 'caller_id'] engageΔ=+0.010 didΔ=+0.013 → **neutral**
- nw_kyc v4 (controller_approved) dims=['schedule'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- ks_cancel v6 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.003 → **neutral**
- nw_renewal v6 (controller_approved) dims=['welcome_message', 'caller_id'] engageΔ=+0.025 didΔ=-0.006 → **beneficial**
- nw_kyc v5 (controller_approved) dims=['caller_id', 'schedule'] engageΔ=+0.000 didΔ=+0.284 → **beneficial**
- nw_renewal v7 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.016 → **neutral**
- ks_cancel v7 (controller_approved) dims=['voice', 'caller_id'] engageΔ=+0.045 didΔ=+0.007 → **beneficial**
- nw_kyc v6 (controller_approved) dims=['schedule'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- nw_renewal v8 (controller_approved) dims=['welcome_message'] engageΔ=+0.062 didΔ=+0.000 → **beneficial**
- nw_renewal v9 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.002 → **neutral**
- ks_cancel v8 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=-0.002 → **neutral**
- nw_renewal v10 (controller_auto) dims=['schedule'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- nw_kyc v7 (controller_approved) dims=['schedule'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- ks_cancel v9 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.009 → **neutral**
- nw_kyc v8 (controller_approved) dims=['schedule'] engageΔ=+0.000 didΔ=+0.000 → **neutral**

## Governance

```
{
  "approval_requests": 15,
  "decisions": {
    "approved": 14,
    "rejected": 1,
    "expired": 0
  },
  "rejection_reasons": {
    "approver declined (judgement call)": 1
  },
  "applied_via_approval": 14,
  "auto_applied": 10,
  "auto_apply_rejected": 0,
  "apply_conflicts": 0,
  "lapsed": 0,
  "peak_requests_per_24h": {
    "nw_renewal": 1,
    "nw_kyc": 1,
    "ks_cancel": 1
  }
}
```

## Incidents

```
[]
```

## Decaying variants — share of in-population calls still on the variant, by day after onset

```
{
  "nw_renewal:welcome_message=W3": {
    "3": 0.208,
    "4": 0.45,
    "5": 0.446,
    "6": 0.023,
    "7": 0.031
  }
}
```

Credits used: 0 · validation runs: 0 · LLM fix calls: 0