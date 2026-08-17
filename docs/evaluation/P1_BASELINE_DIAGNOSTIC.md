# P1 baseline diagnostic — BLUE-0.1.0

**Status:** detector frozen. No retrain. No new features.  
**Goal:** explain why Beneficiary Anomaly and Mule Account Network evade the current Blue Team, and keep those failures as honest Red-Team benchmarks.

Frozen artifact:

- `models/BLUE-0.1.0/blue_team.joblib`
- SHA-256 `66dbe604ad79405a32a320a8e4809d4c0a5a1c98880b1910d834b8bab93c820c`
- Backend: sklearn `HistGradientBoostingClassifier` (`hist_gbdt`)
- Live version string: `BLUE-0.1.0-hist_gbdt-prauc0.360`

Reproduced on the frozen weights, seed `424242`, MEDIUM, 1,000 rows:

| Attack | Generated | Detected @0.5 | Missed | Detection | Precision | Recall | F1 | PR-AUC (mix) | FPR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| BEN-001 Beneficiary Anomaly | 1000 | 1 | 999 | 0.1% | 100% | 0.1% | 0.2% | 98.5% | 0% |
| MUL-001 Mule Account Network | 1000 | 0 | 1000 | 0% | 0% | 0% | 0% | 98.9% | 0% |

These match the UI observations. The high PR-AUC is **not** high detection.

Raw numbers, sweeps, and 100-row samples: `docs/evaluation/p1_baseline_diagnostic.json`, `p1_baseline_sweeps.json`, `ben001_sample100.csv`, `mul001_sample100.csv`. Plots: `docs/evaluation/figures/`.

---

## Root cause

### Beneficiary Anomaly (BEN-001)

**Primary: B feature problem. Secondary: D evaluation problem. Not a threshold problem.**

The attack is a quiet new-payee overlay on otherwise legitimate-looking amounts and devices. The two columns meant to catch it — `beneficiary_is_new` and `destination_concentration` — are in `FEATURE_COLUMNS` and are computed at inference, but they are **not discriminative** in this detector:

1. IEEE legit already has `beneficiary_is_new = 1` on 11.6% of rows (first payment to a payee). IEEE fraud is 10.5% — slightly *lower*. The model has no IEEE reason to treat “new beneficiary” as fraud.
2. IEEE `destination_concentration` is already high (legit median 0.93, 27% exactly 1.0). Painting attack rows to 1.0 does not move them off the legit mass.
3. SHAP on 100 BEN rows: `beneficiary_is_new` mean |SHAP| = 0.022 (near the bottom). The model is looking at `merchant_risk` and `device_age_days`, which this attack does not change.
4. P0 training mix never put `beneficiary_anomaly` rows in the train half (see split). The frozen `per_attack` table already recorded BEN recall **0%** at train time.

Scores sit at ~0.001. Lowering the threshold through the requested 0.01–0.99 sweep never recovers the family (best F1 in that range is 0.6% at 0.01).

### Mule Account Network (MUL-001)

**Primary: B feature problem that is actually a missing graph signal. This is a P2 Network benchmark, already visible in P1.**

The mutation is real at the **entity** layer: 1,000 payments, 884 customers, **2 shared mule beneficiaries**, max fan-in **480 customers**. The detector never sees that. There is no graph, no fan-in count, no shared-beneficiary degree in `FEATURE_COLUMNS`. Row-level `destination_concentration` is saturated at 1.0 for both the overlay and much of IEEE legit. Mule is **not** in `ATTACK_FAMILIES`, so BLUE-0.1.0 was never trained on this family.

Preserve 100% evasion as the Red-Team finding. Do not “fix” it by amplifying amounts.

---

## Evidence

### 1. Model freeze

Copied `models/blue_team.joblib` → `models/BLUE-0.1.0/blue_team.joblib` without fitting. All numbers below are from that file.

Frozen holdout (IEEE 80/20 + P0 synthetics, threshold 0.5):

- LightGBM/HistGB: precision 90.5%, recall 15.2%, F1 26.0%, PR-AUC **0.360**, FPR 0.16%, n=17,000, n_pos=1,560
- Per-family at train time: ATO/VEL/AMT recall ~99–100%; **beneficiary_anomaly recall 0%**, PR-AUC 0.41; low_and_slow recall 0.5%

The UI failure on BEN is the same failure the train-time `per_attack` table already showed.

### 2. Train/test separation and leakage

`FEATURE_COLUMNS` does not contain `attack_id`, `attack_family`, `fraud_label`, `variant_id`, `simulation_id`, `agent_id`, or `intent_id`. `leakage_paths() == []`.

`prepare_split`:

- 80/20 on IEEE rows, stratified on `fraud_label`, seed 424242
- `merchant_risk` fitted on the train slice only (`attach_merchant_risk(train, test)`)
- P0 synthetics concatenated in family order, then **cut in half**: first 1,000 attack rows → train, rest → test

With 400 rows × 5 P0 families, that cut is:

| Split | Families present |
|---|---|
| Train attacks | 400 ATO, 400 VEL, 200 AMT |
| Test attacks | 200 AMT, 400 BEN, 400 SLOW |

**Beneficiary synthetics are entirely in test.** Mule is not a P0 training family at all.

This is not label leakage. It is a training-mix construction issue. It helps explain why BEN was never learned. It is **not** a reason to retrain in this diagnostic.

IEEE prevalence: 80,000 rows, 3.50% fraud.

### 3. Exact evaluation set (Red Team UI)

`RedTeamController.execute` uses two sets:

| Metric in the UI | Set | Prevalence |
|---|---|---|
| Generated / detected / missed / **detection rate** | Attack rows only, threshold 0.5 | 100% fraud |
| Precision, Recall, F1, **PR-AUC**, FPR | Mix = 1,000 attacks + 200 IEEE legit holdout | **83.3% fraud** |

Detection rate is attack-only recall. PR-AUC is mix-set average precision. They answer different questions.

### 4. PR-AUC calculation

`compute_metrics` uses `sklearn.metrics.average_precision_score(y_true, proba)` on the **mix**. Confirmed 0.9845 for BEN, 0.9889 for MUL.

No-skill baseline on that mix is the positive rate **0.833**. Lift over baseline is only **+0.15**. The 98.5% figure is almost “the mix is 83% attacks and attacks rank slightly above legit,” not “the detector catches beneficiaries.”

Attack-only PR-AUC is degenerate (all labels = 1) and reports 1.0. The UI does not use that number.

Train-time BEN PR-AUC on a **balanced-ish** mix (800 legit + 400 BEN) was **0.41** — the honest ranking number for this family.

ROC-AUC on the Red Team mix is ~0.95 because attack median score (0.00106) > legit median (0.00013). Ranking exists in the 10⁻⁴ band. It does not cross 0.5.

---

## Threshold analysis

Sweep: 0.01, 0.02, …, 0.99 on the mix set. Full table: `docs/evaluation/p1_baseline_sweeps.json`. Plots: `docs/evaluation/figures/BEN-001_threshold_sweep.svg`, `MUL-001_threshold_sweep.svg`.

### BEN-001 mix (1,000 attack + 200 legit)

| Threshold | Precision | Recall | F1 | FPR |
|---:|---:|---:|---:|---:|
| 0.01 | 100% | 0.3% | 0.6% | 0% |
| 0.02 | 100% | 0.1% | 0.2% | 0% |
| 0.50 | 100% | 0.1% | 0.2% | 0% |
| 0.99 | 0% | 0% | 0% | 0% |

Best F1 in 0.01–0.99 is at **0.01** (0.6%). One BEN row scores 0.986; 999 score below 0.01 (p90 = 0.0020).

**Not A (threshold).** The operating point 0.5 is not hiding a usable policy inside 0.01–0.99. Recovering the family would require a threshold **below** 0.01, overlapping the legit tail (legit p90 = 0.00037, attack p10 = 0.00032). That is not a robust Blue-Team policy; it is score collapse.

### MUL-001 mix

| Threshold | Precision | Recall | F1 | FPR |
|---:|---:|---:|---:|---:|
| 0.01 | 100% | 0.4% | 0.8% | 0% |
| 0.50 | 0% | 0% | 0% | 0% |

Attack max score = 0.036. Nothing reaches 0.5. Same conclusion: not a 0.5-vs-0.3 threshold bug.

PR curves: `docs/evaluation/figures/BEN-001_pr_curve.svg`, `MUL-001_pr_curve.svg`. Both hug high precision because prevalence is 83% and FPR at every requested threshold is 0.

---

## Feature analysis

Both columns **are** model features:

```
FEATURE_COLUMNS includes beneficiary_is_new, destination_concentration
```

They are filled with 0.0 if missing, then passed through `feature_matrix` at train and at `BlueTeam.score`. Same function, same column order.

### How they are calculated

**IEEE / legit (`add_behavior_features`):**

- `destination_concentration` = count(customer, beneficiary) / count(customer) over the batch
- `beneficiary_is_new` = 1 if this is the customer’s first timestamp with that beneficiary

**P1 mutation (`apply_mutation`):**

- New `beneficiary_id`s are written
- `beneficiary_is_new` is **set to 1.0** on changed rows
- `destination_concentration` is **not recomputed from the new IDs**; `dest_concentration_delta` is added to the pre-mutation value and clipped to 1.0

Train and inference use the same `feature_matrix`. The inconsistency is **simulator vs graph reality**, not train vs score.

### Distributions

IEEE (80k):

| Slice | `beneficiary_is_new` mean | `destination_concentration` median | frac dest = 1 |
|---|---:|---:|---:|
| Legit | 0.116 | 0.935 | 0.273 |
| IEEE fraud | 0.105 | 0.945 | 0.414 |

BEN-001 MEDIUM vs IEEE legit holdout (n=200):

| Feature | Attack overlay | Recomputed from IDs | Legit holdout |
|---|---:|---:|---:|
| `beneficiary_is_new` mean | 1.00 | 1.00 | 0.125 |
| `destination_concentration` mean | 1.00 | 0.884 | 0.850 |

Mean |overlay − recomputed| for dest concentration = **0.116**. The model is scored on the painted 1.0, which is already the legit mode.

MUL-001: overlay dest = 1.00 vs recomputed 0.94 vs legit 0.85. Fan-in does not appear in the scalar.

### SHAP (TreeExplainer, 100 attack rows)

BEN-001 mean |SHAP|:

| Rank | Feature | mean \|SHAP\| |
|---:|---|---:|
| 1 | merchant_risk | 3.82 |
| 2 | device_age_days | 2.03 |
| 3 | transaction_count_1h | 0.70 |
| 4 | amount_deviation | 0.37 |
| 5 | amount | 0.28 |
| 6 | destination_concentration | 0.21 |
| … | beneficiary_is_new | **0.022** |

MUL-001: same top three (`merchant_risk`, `device_age_days`, `transaction_count_1h`). `beneficiary_is_new` = 0.030. The mule graph is invisible.

---

## Attack realism analysis

### BEN-001 (100 rows: `docs/evaluation/ben001_sample100.csv`)

MEDIUM / BEN-V01: `beneficiary_change_probability=1.0`, `dest_concentration_delta=0.28`, `merchant_change_probability=0.5`.

Inspected pattern:

- Amounts stay in-band (tens to low hundreds) — looks like the customer’s usual spend
- Devices, velocity, failed auth unchanged
- Every row gets a fresh `mut-ben-*` id and `beneficiary_is_new=1`
- About half the merchants become `mut-merch-*`
- 884 customers, 944 beneficiaries — this is **not** a mule network; it is one-to-one new payees
- Scores ~0.0002–0.002 except one outlier

That is a realistic **quiet new-payee** pattern. It is not a loud amount/velocity attack. The simulator is doing the job P1 asked for. The weakness is that the Blue Team’s learned features ignore that job.

Caveat (C, minor): dest concentration is painted rather than recomputed. Fixing that without a new graph feature would still land near 1.0, which IEEE already uses. Do not treat a dest-recompute patch as a detection fix.

### MUL-001 (100 rows: `docs/evaluation/mul001_sample100.csv`)

MEDIUM / MUL-V01: `share_beneficiary=True`, `cluster_count=5` merged with variant overlay → **2 mule ids** in this run (`mule-ben-2816-1`, `mule-ben-7540-0`).

- Many distinct customers pay the same two beneficiaries
- Max fan-in 480 — that **is** a mule network
- `account_age_days` scaled down on some rows
- Amounts still mostly in-band
- Every score in the sample is ~0.001

Realism at the entity layer is good. Realism at the **feature** layer is incomplete: the model cannot see fan-in. That incompleteness is the P2 gap, not a reason to discard the attack.

---

## Model analysis

BLUE-0.1.0 is a conservative tree model. Frozen holdout FPR is 0.16% and recall is 15%. It fires on P0 families that move amount, velocity, device age, and failed auth. It does not fire on beneficiary/mule overlays that leave those axes alone.

SHAP agrees: `merchant_risk` and `device_age_days` dominate even on BEN/MUL rows, i.e. the model is explaining *absence of ATO-like signal*, not payee structure.

Policy thresholds (`ALLOW 0.30 / STEP_UP 0.60 / REVIEW 0.80`) are all far above the BEN/MUL score mass. Changing policy cutoffs inside the usual 0.3–0.8 band would not catch these families.

---

## Why the attacks bypass BLUE-0.1.0

**BEN-001.** New payee + dest=1.0 on otherwise normal spend. Those two channels are (a) common in legit IEEE, (b) nearly unused by the tree, (c) not present as synthetics in the train half. The detector therefore assigns ~0.001, the same order as legit, and 0.5 never triggers. Precision 100% / FPR 0% because almost nothing is flagged; the single 0.986 score is a true positive. PR-AUC 98.5% is an 83%-prevalence mix artifact.

**MUL-001.** The crime is shared infrastructure (2 mule accounts, hundreds of customers). BLUE-0.1.0 is a per-row classifier. It never received mule synthetics in training. Row features look like slightly younger accounts paying concentrated dests — a description that also fits a large fraction of legit IEEE. Max score 0.036. 100% evasion at 0.5 is the correct measurement.

---

## Failure class

| | BEN-001 | MUL-001 |
|---|---|---|
| **A. Threshold** | No. Sweep 0.01–0.99 never recovers the family. | No. Max score 0.036. |
| **B. Feature** | **Yes.** Payee features present but non-informative / unused. | **Yes.** Fan-in exists in IDs, absent from features. |
| **C. Simulation** | Minor dest-paint vs recompute. Attack still a valid quiet new-payee. | Entity graph is realistic. Feature layer does not encode it. |
| **D. Evaluation** | **Yes, for PR-AUC.** 98.5% is mix prevalence 83%, not detection. Detection 0.1% is the real operating metric. Train-time BEN PR-AUC 0.41 is the fair ranking number. | Same mix-set PR-AUC inflation. 0% detection is the real metric. |

---

## P1 vs P2

**Keep both as P1 Red-Team benchmarks.** Do not raise detection by making the overlay louder.

| Family | Keep in P1? | Promote to P2 Network/Geo? |
|---|---|---|
| BEN-001 | Yes. Tabular new-payee attack. Honest miss for a row model. A later Blue V2 *may* reweight `beneficiary_is_new` or train with BEN in the mix — still P1 tabular. | Only if we add payee-graph features (new-payee rate in a window, beneficiary degree). Not required to keep the benchmark. |
| MUL-001 | Yes, as the P1 overlay that **exposes** the gap. | **Yes.** Shared mule fan-in is the P2 network task. Graph edges already exist in `graph_edges`; they are not in the detector. |

Closed-loop retrain (Model V2 on the same seeds) should wait until this baseline is accepted. Any later lift must be reported as BLUE-0.2.x vs this freeze, same contracts, same seeds.

---

## What not to do next

- Do not drop the decision threshold to 0.001 to “fix” recall.
- Do not raise BEN/MUL `amount_deviation` so the current tree notices them.
- Do not treat mix-set PR-AUC as the P1 detection KPI for these families.
- Do not retrain in the same commit as this diagnostic.

Valid next choices, after this report is accepted:

1. Leave the misses in the leaderboard as Red-Team wins against BLUE-0.1.0.
2. Schedule P2 graph features for mule fan-in.
3. If a P1 Blue tweak is desired later: put BEN (and SLOW) in the **train** mix and re-evaluate on the frozen seeds — new version id, same diagnostic protocol.
