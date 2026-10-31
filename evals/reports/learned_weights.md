# Learned rule weights (ML step 1)

> Synthetic labelled data (evals/generate.py). The model learns how much each existing rule should count on simulated scenarios; it is a calibration of the rules, not a fraud probability and not real-world accuracy.

Trained on D2 (seed 2) (1066 scored units, 166 fraud); tested on fresh held-out seed 4 (1018 units, 169 fraud). Alert volume is matched to the hand weights on D2, so the comparison is like for like.

## Held-out comparison

| Measure | Hand weights | Learned weights (logistic) | Boosted trees |
| --- | --- | --- | --- |
| Ranking quality (average precision, units) | 0.785 | 0.951 | 0.884 |
| Fraud incidents caught at Medium+ | 89% | 89% | 93% |
| Fraud incidents caught at High | 55% | 54% | 50% |
| Lookalikes wrongly at Medium+ | 12% | 8% | 25% |
| Lookalikes wrongly at High | 0% | 0% | 8% |
| Precision of Medium+ alerts | 73% | 85% | 79% |
| Background false alarms (Medium+) | 41 | 22 | 16 |
| Medium+ alerts per 1,000 events | 6.17 | 6.1 | 7.39 |

## What the model learned

Multiplier on the hand weight: 1.0 = hand weight confirmed, above 1 = rule deserves more, 0 = adds nothing on D2.

| Rule | Direction | Learned multiplier | Units with this rule (D2) |
| --- | --- | --- | --- |
| MT-KNOWN | mitigation | 1.51 | 472 |
| MT-TENURE | mitigation | 1.34 | 1003 |
| TX-01 | risk | 1.29 | 363 |
| TX-03 | risk | 1.27 | 505 |
| MT-RECUR | mitigation | 1.21 | 199 |
| MT-OWN | mitigation | 1.12 | 12 |
| MT-PAYEE | mitigation | 1.12 | 215 |
| AP-04 | risk | 1.09 | 5 |
| ID-01 | risk | 1.09 | 12 |
| ID-02 | risk | 1.08 | 4 |
| TX-08 | risk | 1.06 | 6 |
| DV-02 | risk | 1.02 | 6 |
| MT-HOUSE | mitigation | 1.02 | 4 |
| TX-05 | risk | 1.02 | 19 |
| TX-09 | risk | 1.02 | 8 |
| AP-01 | risk | 1.01 | 8 |
| AP-02 | risk | 1.01 | 8 |
| DV-01 | risk | 1.01 | 10 |
| NW-02 | risk | 1.01 | 4 |
| CHAIN_FLOOR | floor | 1.0 | 8 |
| HV-01 | risk | 1.0 | 0 |
| LG-03 | risk | 1.0 | 4 |
| DV-03 | risk | 0.99 | 12 |
| LG-01 | risk | 0.99 | 10 |
| LG-02 | risk | 0.99 | 12 |
| TX-07 | risk | 0.99 | 2 |
| TX-06 | risk | 0.87 | 103 |
| TX-04 | risk | 0.86 | 112 |
| NW-01 | risk | 0.61 | 181 |

## What the boosted trees rely on (permutation importance on D2)

Drop in average precision when a rule's evidence is shuffled; larger = the model relies on it more.

| Rule | Importance |
| --- | --- |
| MT-TENURE | 0.3504 |
| TX-03 | 0.2834 |
| MT-KNOWN | 0.2381 |
| TX-01 | 0.0738 |

Rules are frozen for Stage 1: these multipliers are evidence for a future rules change, reviewed by a person and re-checked on new held-out data before adoption.
