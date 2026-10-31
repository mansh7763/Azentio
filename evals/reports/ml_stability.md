# Learned weights: stability across datasets

> Synthetic labelled data (evals/generate.py). The model learns how much each existing rule should count on simulated scenarios; it is a calibration of the rules, not a fraud probability and not real-world accuracy.

Trained on pooled seeds [2, 6, 7] (3097 units, 512 fraud, 272 incidents). Tested on unseen seeds [4, 5, 8]; each cell is the mean (lowest–highest) over the three test datasets, at the alert volume matched on the training data.

| Measure | Hand weights | Learned weights |
| --- | --- | --- |
| Ranking quality (average precision) | 0.78 (0.777–0.785) | 0.952 (0.949–0.954) |
| Fraud incidents caught at Medium+ | 89% (88%–91%) | 89% (88%–91%) |
| Fraud incidents caught at High | 54% (54%–55%) | 51% (48%–55%) |
| Lookalikes wrongly at Medium+ | 10% (8%–12%) | 8% (8%–8%) |
| Precision of Medium+ alerts | 76% (73%–78%) | 88% (85%–90%) |
| Background false alarms | 35 (29–41) | 16.667 (12–21) |
| Medium+ alerts per 1,000 events | 5.857 (5.56–6.17) | 5.927 (5.66–6.07) |

## Rule multipliers with 90% intervals (50 bootstrap resamples by incident)

| Rule | Multiplier | 90% interval | Units | Verdict |
| --- | --- | --- | --- | --- |
| MT-KNOWN | 1.53 | 1.47–1.58 | 1396 | stronger than hand weight |
| MT-TENURE | 1.33 | 1.25–1.4 | 2905 | stronger than hand weight |
| TX-01 | 1.3 | 1.22–1.37 | 1009 | stronger than hand weight |
| TX-03 | 1.24 | 1.15–1.31 | 1509 | stronger than hand weight |
| MT-RECUR | 1.2 | 1.14–1.25 | 561 | stronger than hand weight |
| MT-OWN | 1.13 | 1.09–1.18 | 36 | stronger than hand weight |
| MT-PAYEE | 1.12 | 1.1–1.15 | 596 | stronger than hand weight |
| AP-04 | 1.1 | 1.05–1.14 | 17 | stronger than hand weight |
| ID-01 | 1.09 | 1.04–1.12 | 39 | not distinguishable from hand weight |
| ID-02 | 1.08 | 1.05–1.11 | 12 | not distinguishable from hand weight |
| TX-08 | 1.05 | 1.02–1.07 | 22 | not distinguishable from hand weight |
| DV-02 | 1.02 | 1.01–1.03 | 17 | not distinguishable from hand weight |
| MT-HOUSE | 1.02 | 1.01–1.03 | 12 | not distinguishable from hand weight |
| TX-09 | 1.02 | 1.01–1.03 | 27 | not distinguishable from hand weight |
| AP-01 | 1.01 | 1.01–1.02 | 27 | not distinguishable from hand weight |
| AP-02 | 1.01 | 1.0–1.01 | 27 | not distinguishable from hand weight |
| DV-01 | 1.01 | 1.0–1.02 | 29 | not distinguishable from hand weight |
| NW-02 | 1.01 | 1.0–1.01 | 12 | not distinguishable from hand weight |
| AP-03 | 1.0 | 1.0–1.0 | 5 | not distinguishable from hand weight |
| CHAIN_FLOOR | 1.0 | 1.0–1.0 | 24 | not distinguishable from hand weight |
| HV-01 | 1.0 | 1.0–1.0 | 0 | not distinguishable from hand weight |
| LG-03 | 1.0 | 1.0–1.0 | 12 | not distinguishable from hand weight |
| TX-05 | 1.0 | 0.98–1.01 | 63 | not distinguishable from hand weight |
| DV-03 | 0.99 | 0.98–0.99 | 36 | not distinguishable from hand weight |
| LG-01 | 0.99 | 0.99–1.0 | 31 | not distinguishable from hand weight |
| LG-02 | 0.99 | 0.99–1.0 | 36 | not distinguishable from hand weight |
| TX-07 | 0.99 | 0.98–1.0 | 4 | not distinguishable from hand weight |
| TX-06 | 0.9 | 0.86–0.95 | 283 | weaker than hand weight |
| TX-04 | 0.89 | 0.85–0.93 | 312 | weaker than hand weight |
| NW-01 | 0.58 | 0.54–0.62 | 542 | weaker than hand weight |

The pooled model is the engine's shadow model (backend/app/detect/ml_model.json); rule scores are unchanged.
