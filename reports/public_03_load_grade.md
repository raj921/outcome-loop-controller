# Grade report — public_03_load

## Outcomes vs baseline (no-op controller)

| workflow | conclusion rate | Δ | pickup | Δ | engagement | Δ | engagement gap captured | hallucinated calls (base) |
|---|---|---|---|---|---|---|---|---|
| arav_cancel_2 | 0.396 | +17.4% | 0.261 | +7.4% | 0.533 | +7.4% | 50% | 435 (409) |
| arav_kyc_1 | 0.406 | +13.2% | 0.239 | +11.1% | 0.597 | -0.6% | 0% | 375 (352) |
| arav_renewal_0 | 0.479 | +18.2% | 0.284 | +7.5% | 0.595 | +8.5% | 47% | 464 (408) |
| kest_cancel_2 | 0.396 | +17.7% | 0.261 | +7.8% | 0.534 | +7.0% | 50% | 423 (418) |
| kest_kyc_1 | 0.437 | +22.9% | 0.256 | +19.4% | 0.594 | -0.6% | 0% | 463 (370) |
| kest_renewal_0 | 0.473 | +17.6% | 0.281 | +6.1% | 0.591 | +8.5% | 46% | 426 (403) |
| nort_cancel_2 | 0.401 | +18.2% | 0.262 | +7.5% | 0.535 | +7.4% | 51% | 470 (368) |
| nort_kyc_1 | 0.474 | +33.4% | 0.274 | +27.2% | 0.595 | -0.1% | 0% | 433 (318) |
| nort_renewal_0 | 0.476 | +17.4% | 0.284 | +7.5% | 0.591 | +7.8% | 42% | 471 (419) |
| tide_cancel_2 | 0.393 | +14.6% | 0.261 | +6.8% | 0.530 | +5.8% | 44% | 386 (401) |
| tide_kyc_1 | 0.438 | +22.8% | 0.256 | +19.3% | 0.595 | -0.5% | 0% | 416 (376) |
| tide_renewal_0 | 0.479 | +18.3% | 0.284 | +7.6% | 0.593 | +8.7% | 47% | 505 (425) |
| ALL | 0.437 | +19.3% | 0.267 | +10.8% | 0.574 | +5.2% | 30% | 5267 (4667) |

## Changes applied by the controller

52 applied — neutral: 24, beneficial: 28

- kest_cancel_2 v2 (controller_approved) dims=['cohorts', 'welcome_message', 'voice', 'caller_id', 'schedule'] engageΔ=-0.003 didΔ=+0.007 → **neutral**
- arav_cancel_2 v2 (controller_approved) dims=['cohorts', 'welcome_message', 'voice', 'caller_id', 'schedule'] engageΔ=-0.003 didΔ=+0.007 → **neutral**
- tide_cancel_2 v2 (controller_approved) dims=['cohorts', 'welcome_message', 'voice', 'caller_id', 'schedule'] engageΔ=-0.003 didΔ=+0.007 → **neutral**
- nort_cancel_2 v2 (controller_approved) dims=['cohorts', 'welcome_message', 'voice', 'caller_id', 'schedule'] engageΔ=-0.003 didΔ=+0.007 → **neutral**
- nort_renewal_0 v2 (controller_approved) dims=['cohorts', 'welcome_message', 'voice', 'caller_id', 'schedule'] engageΔ=+0.041 didΔ=-0.011 → **beneficial**
- kest_renewal_0 v2 (controller_approved) dims=['cohorts', 'welcome_message', 'voice', 'caller_id', 'schedule'] engageΔ=+0.040 didΔ=-0.011 → **beneficial**
- arav_renewal_0 v2 (controller_approved) dims=['cohorts', 'welcome_message', 'voice', 'caller_id', 'schedule'] engageΔ=+0.041 didΔ=-0.011 → **beneficial**
- nort_renewal_0 v3 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.063 → **beneficial**
- kest_renewal_0 v3 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.018 → **neutral**
- arav_renewal_0 v3 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.063 → **beneficial**
- arav_kyc_1 v2 (controller_approved) dims=['cohorts', 'caller_id', 'schedule'] engageΔ=+0.000 didΔ=+0.063 → **beneficial**
- tide_renewal_0 v2 (controller_approved) dims=['cohorts', 'welcome_message', 'voice', 'caller_id', 'schedule'] engageΔ=+0.041 didΔ=-0.010 → **beneficial**
- tide_kyc_1 v2 (controller_approved) dims=['cohorts', 'caller_id', 'schedule'] engageΔ=+0.000 didΔ=+0.063 → **beneficial**
- nort_kyc_1 v2 (controller_approved) dims=['cohorts', 'caller_id', 'schedule'] engageΔ=+0.000 didΔ=+0.065 → **beneficial**
- kest_kyc_1 v2 (controller_approved) dims=['cohorts', 'caller_id', 'schedule'] engageΔ=+0.000 didΔ=+0.065 → **beneficial**
- tide_renewal_0 v3 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.065 → **beneficial**
- nort_cancel_2 v3 (controller_approved) dims=['welcome_message', 'voice', 'caller_id'] engageΔ=+0.099 didΔ=+0.037 → **beneficial**
- nort_renewal_0 v4 (controller_approved) dims=['welcome_message'] engageΔ=+0.067 didΔ=+0.000 → **beneficial**
- kest_cancel_2 v3 (controller_approved) dims=['welcome_message', 'voice', 'caller_id'] engageΔ=+0.106 didΔ=+0.038 → **beneficial**
- arav_renewal_0 v4 (controller_approved) dims=['welcome_message'] engageΔ=+0.090 didΔ=+0.000 → **beneficial**
- arav_cancel_2 v3 (controller_approved) dims=['welcome_message', 'voice', 'caller_id'] engageΔ=+0.106 didΔ=+0.038 → **beneficial**
- tide_cancel_2 v3 (controller_approved) dims=['voice', 'caller_id'] engageΔ=+0.061 didΔ=+0.038 → **beneficial**
- tide_renewal_0 v4 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=+0.093 didΔ=+0.000 → **beneficial**
- nort_kyc_1 v3 (controller_approved) dims=['caller_id', 'schedule'] engageΔ=+0.000 didΔ=+0.506 → **beneficial**
- kest_renewal_0 v4 (controller_approved) dims=['welcome_message', 'voice', 'caller_id'] engageΔ=+0.107 didΔ=+0.047 → **beneficial**
- nort_renewal_0 v5 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=+0.014 didΔ=+0.000 → **beneficial**
- kest_renewal_0 v5 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=+0.004 didΔ=+0.000 → **neutral**
- nort_kyc_1 v4 (controller_approved) dims=['schedule'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- nort_cancel_2 v4 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=+0.007 didΔ=+0.000 → **neutral**
- tide_renewal_0 v5 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=+0.016 didΔ=+0.000 → **beneficial**
- kest_kyc_1 v3 (controller_approved) dims=['caller_id', 'schedule'] engageΔ=+0.000 didΔ=+0.460 → **beneficial**
- tide_kyc_1 v3 (controller_approved) dims=['caller_id', 'schedule'] engageΔ=+0.000 didΔ=+0.460 → **beneficial**
- tide_cancel_2 v4 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=+0.044 didΔ=+0.000 → **beneficial**
- arav_renewal_0 v5 (controller_approved) dims=['welcome_message', 'voice', 'caller_id'] engageΔ=+0.008 didΔ=+0.010 → **neutral**
- arav_cancel_2 v4 (controller_approved) dims=['welcome_message'] engageΔ=+0.001 didΔ=+0.000 → **neutral**
- kest_cancel_2 v4 (controller_approved) dims=['welcome_message'] engageΔ=+0.001 didΔ=+0.000 → **neutral**
- arav_kyc_1 v3 (controller_approved) dims=['caller_id', 'schedule'] engageΔ=+0.000 didΔ=+0.428 → **beneficial**
- nort_kyc_1 v5 (controller_approved) dims=['schedule'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- kest_renewal_0 v6 (controller_approved) dims=['voice'] engageΔ=+0.003 didΔ=+0.000 → **neutral**
- arav_renewal_0 v6 (controller_approved) dims=['voice', 'caller_id'] engageΔ=+0.012 didΔ=+0.011 → **beneficial**
- nort_renewal_0 v6 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=+0.017 didΔ=+0.000 → **beneficial**
- kest_kyc_1 v4 (controller_approved) dims=['schedule'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- tide_renewal_0 v6 (controller_approved) dims=['voice'] engageΔ=+0.003 didΔ=+0.000 → **neutral**
- nort_renewal_0 v7 (controller_approved) dims=['voice'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- arav_cancel_2 v5 (controller_approved) dims=['welcome_message'] engageΔ=+0.001 didΔ=+0.000 → **neutral**
- tide_renewal_0 v7 (controller_approved) dims=['voice'] engageΔ=+0.004 didΔ=+0.000 → **neutral**
- nort_kyc_1 v6 (controller_approved) dims=['schedule'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- kest_renewal_0 v7 (controller_approved) dims=['voice'] engageΔ=+0.002 didΔ=+0.000 → **neutral**
- arav_renewal_0 v7 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=+0.002 didΔ=+0.000 → **neutral**
- kest_kyc_1 v5 (controller_approved) dims=['schedule'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- arav_kyc_1 v4 (controller_approved) dims=['schedule'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- tide_kyc_1 v4 (controller_approved) dims=['schedule'] engageΔ=+0.000 didΔ=+0.000 → **neutral**

## Governance

```
{
  "approval_requests": 54,
  "decisions": {
    "approved": 48,
    "rejected": 6,
    "expired": 0
  },
  "rejection_reasons": {
    "approver declined (judgement call)": 6
  },
  "applied_via_approval": 48,
  "auto_applied": 4,
  "auto_apply_rejected": 0,
  "apply_conflicts": 0,
  "lapsed": 0,
  "peak_requests_per_24h": {
    "nort_renewal_0": 1,
    "nort_kyc_1": 1,
    "nort_cancel_2": 1,
    "kest_renewal_0": 2,
    "kest_kyc_1": 1,
    "kest_cancel_2": 1,
    "arav_renewal_0": 1,
    "arav_kyc_1": 1,
    "arav_cancel_2": 1,
    "tide_renewal_0": 2,
    "tide_kyc_1": 1,
    "tide_cancel_2": 1
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
  "nort_renewal_0:welcome_message=W3": {
    "3": 0.736,
    "4": 0.746
  },
  "kest_renewal_0:welcome_message=W3": {
    "3": 0.944,
    "4": 0.942
  },
  "arav_renewal_0:welcome_message=W3": {
    "3": 0.906,
    "4": 0.911
  },
  "tide_renewal_0:welcome_message=W3": {
    "3": 0.945,
    "4": 0.942
  }
}
```

Credits used: 0 · validation runs: 0 · LLM fix calls: 0