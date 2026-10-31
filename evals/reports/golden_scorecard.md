# Golden scorecard

> Hand-built calibration scenarios, written alongside the rules. They show the rules behave as designed; they are not an accuracy measurement.

Rules version `1b9277a88059` · run `RUN-56f2b6a80b` · **34 / 34 scenarios behave as designed**

| Group | Passed |
| --- | --- |
| must flag | 7 / 7 |
| capped | 8 / 8 |
| lookalike, must stay Low | 15 / 15 |
| must stay silent | 4 / 4 |

Alerts on entities no scenario mentions: 25 (10 at Medium or High: BURST-C004-L-C004-F0 (Medium 55), T-C006-F0 (Medium 59), T-C006-F1 (Medium 59), T-C006-F2 (Medium 59), T-C006-F3 (High 70), T-C006-F4 (High 82), T-C021-PAY0-3 (Medium 45), T-C021-PAY0-4 (Medium 67), T-C021-PAY1-4 (Medium 40), T-C021-PAY2-4 (Medium 40)). Unreviewed: **0** (reasons for the reviewed ones: `evals/reviewed_unexpected.yaml`).

| Scenario | Group | Unit · entity | Expected | Actual | Top contributions | Result |
| --- | --- | --- | --- | --- | --- | --- |
| LK-T5 | lookalike, must stay Low | transaction · T-C001-NEW | <= Low | no alert | — | ✅ |
| LK-T7-M0 | lookalike, must stay Low | transaction · T-C001-M0 | <= Low | no alert | — | ✅ |
| LK-T7-M1 | lookalike, must stay Low | transaction · T-C001-M1 | <= Low | Low 22 | TX-01 +22 | ✅ |
| LK-T7-M2 | lookalike, must stay Low | transaction · T-C001-M2 | <= Low | Low 22 | TX-01 +22 | ✅ |
| LK-T7-M3 | lookalike, must stay Low | transaction · T-C001-M3 | <= Low | Low 4 | TX-01 +23, MT-PAYEE -10, MT-RECUR -7 | ✅ |
| LK-T7-M4 | lookalike, must stay Low | transaction · T-C001-M4 | <= Low | Low 4 | TX-01 +23, MT-PAYEE -10, MT-RECUR -7 | ✅ |
| LK-T6 | must flag | transaction · T-C002-ATO | High | High 85 | CHAIN:ato_full +33, LG-02 +31, DV-03 +21 | ✅ |
| LG-T6 | capped | login_burst ·  | <= Medium | Medium 55 | LG-02 +30, DV-03 +21, CHAIN:ato_partial +4 | ✅ |
| LG-T7 | capped | transaction · T-C004-BIG | <= Medium | Medium 45 | TX-01 +45 | ✅ |
| TX-T1 | must flag | transaction · T-C005-BIG | >= Medium | Medium 59 | TX-01 +40, TX-03 +19 | ✅ |
| TX-T2 | must flag | transaction · T-C006-F5 | High | High 80 | TX-05 +29, TX-01 +26, TX-04 +25 | ✅ |
| TX-T4 | must stay silent | transaction · T-C007-EMI | no alert | no alert | — | ✅ |
| DV-T2 | lookalike, must stay Low | device_cluster · DEV-HOME | <= Low | Low 18 | DV-01 +45, MT-HOUSE -27 | ✅ |
| AP-T1-C011 | must flag | application · APP-C011 | High | High 80 | AP-01 +40, ID-01 +22, AP-02 +18 | ✅ |
| AP-T1-C012 | must flag | application · APP-C012 | High | High 80 | AP-01 +40, ID-01 +22, AP-02 +18 | ✅ |
| AP-T1-early-C010 | capped | application · APP-C010 | <= Medium | no alert | — | ✅ |
| AP-T1-early-C013 | capped | application · APP-C013 | <= Medium | Low 35 | ID-01 +35 | ✅ |
| DV-T1 | must flag | device_cluster · DEV-RING | High | High 72 | DV-02 +38, DV-01 +34 | ✅ |
| G7-C016 | lookalike, must stay Low | application · APP-C016 | <= Low | no alert | — | ✅ |
| G7-C017 | lookalike, must stay Low | application · APP-C017 | <= Low | no alert | — | ✅ |
| G7-C018 | lookalike, must stay Low | application · APP-C018 | <= Low | no alert | — | ✅ |
| G3-usual-device | lookalike, must stay Low | transaction · T-C019-RENT | <= Low | Low 10 | LG-02 +35, MT-PAYEE -18, MT-KNOWN -4 | ✅ |
| LG-T8 | capped | login_burst ·  | <= Medium | Low 30 | LG-01 +30 | ✅ |
| LK-T2-salary | must stay silent | transaction · T-C022-SAL6 | no alert | no alert | — | ✅ |
| LK-T2-rent | lookalike, must stay Low | transaction · T-C022-RENT6 | <= Low | no alert | — | ✅ |
| LK-T3 | lookalike, must stay Low | transaction · T-C023-TRIP | <= Low | no alert | — | ✅ |
| LK-T4-0 | capped | transaction · T-C024-FEST0 | <= Medium | Medium 45 | TX-01 +45 | ✅ |
| LK-T4-1 | capped | transaction · T-C024-FEST1 | <= Medium | Medium 43 | TX-01 +43 | ✅ |
| LK-T4-2 | capped | transaction · T-C024-FEST2 | <= Medium | Low 33 | TX-01 +33 | ✅ |
| AP-T2-0 | must stay silent | application · APP-C025-0 | no alert | no alert | — | ✅ |
| AP-T2-1 | must stay silent | application · APP-C025-1 | no alert | no alert | — | ✅ |
| G5-payroll | lookalike, must stay Low | transaction · T-C021-PAY6-4 | <= Low | Low 7 | TX-04 +40, MT-PAYEE -17, MT-RECUR -13 | ✅ |
| G12-mule | must flag | transaction · T-C011-OUT2 | High | High 80 | AP-03 +50, CHAIN:loan_mule +30 | ✅ |
| G12-benign | lookalike, must stay Low | transaction · T-C016-SUP | <= Low | no alert | — | ✅ |
