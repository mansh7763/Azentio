# Held-out evaluation (D3 (seed 3, held out))

> Synthetic data from evals/generate.py with planted, labelled incidents. These numbers measure the rules against the scenarios we know how to simulate; they are not real-world fraud detection rates.

Rules version `d88c05508daf` · rows {'customers': 249, 'accounts': 257, 'transactions': 16922, 'logins': 11087, 'applications': 61}

| Measure | Value |
| --- | --- |
| Fraud incidents caught at Medium or High | 93% of 56 |
| Fraud incidents caught at High | 57% |
| Lookalikes wrongly raised to Medium or High | 8% of 48 |
| Lookalikes wrongly raised to High | 0% |
| Precision of Medium/High alerts | 50% |
| Background false alarms (Medium/High, no planted incident) | 36 |
| Medium/High alerts per 1,000 events (analyst workload) | 9.48 |
| Recall, new customers (cold start) | 100% of 16 |
| Recall, established customers | 90% |

| Scenario | Kind | Incidents | At Medium+ | At High |
| --- | --- | --- | --- | --- |
| account_takeover | fraud | 4 | 4 | 4 |
| circular_flow | fraud | 4 | 4 | 4 |
| device_ring | fraud | 4 | 4 | 4 |
| dormant_awakening | fraud | 4 | 4 | 4 |
| identity_reuse | fraud | 4 | 4 | 0 |
| loan_to_mule | fraud | 4 | 4 | 2 |
| mule_dispersal | fraud | 8 | 8 | 6 |
| payout_swarm | fraud | 4 | 4 | 0 |
| recipient_convergence | fraud | 4 | 4 | 4 |
| scam_payment | fraud | 4 | 4 | 0 |
| slow_drain | fraud | 4 | 0 | 0 |
| structuring | fraud | 4 | 4 | 0 |
| takeover_attempt | fraud | 4 | 4 | 4 |
| business_payroll | lookalike | 4 | 0 | 0 |
| family_landline | lookalike | 4 | 0 | 0 |
| forgot_password | lookalike | 4 | 0 | 0 |
| household_device | lookalike | 4 | 0 | 0 |
| loan_paid_to_supplier | lookalike | 4 | 4 | 0 |
| merchant_collection | lookalike | 4 | 0 | 0 |
| new_phone | lookalike | 4 | 0 | 0 |
| office_colleagues | lookalike | 4 | 0 | 0 |
| own_account_sweep | lookalike | 4 | 0 | 0 |
| regular_large_payment | lookalike | 4 | 0 | 0 |
| seasonal_return | lookalike | 4 | 0 | 0 |
| shopping_spree | lookalike | 4 | 0 | 0 |
