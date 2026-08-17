# `docs/ML_EVALUATION.md`

Copy this into:

```
docs/ML_EVALUATION.md
```

This document defines how to evaluate:

- The Blue-Team detector.
- The Red-Team simulator.
- Network and agent attacks.
- Novelty and fidelity.
- The closed-loop improvement.

```
# Adversarial Payment Defense Lab

## ML Evaluation Specification

Version: 0.1.0  
Status: Draft  
Owner: FraudForge Engineering

---

## 1. Purpose

This document defines the evaluation framework for the Adversarial Payment Defense Lab.

The evaluation must answer:

1. Can the Blue Team detect fraudulent transactions?
2. Can the Blue Team detect coordinated fraud networks?
3. Can the Blue Team detect agent and intent violations?
4. Are synthetic attacks realistic?
5. Are generated attacks diverse?
6. Are novel attacks different from historical attacks?
7. Can the Red Team bypass the initial detector?
8. Does the Blue Team improve after learning from Red-Team failures?
9. Can the system make decisions with acceptable latency?
10. Are explanations and mitigations correct and useful?

The evaluation must separate:

```text
Detection quality
Attack-generation quality
Network quality
Agent/intent security
Operational quality
Closed-loop improvement
```

---

## 2. Evaluation Principles

### 2.1 Time-aware evaluation

Payment fraud evolves over time. Training data must precede validation data, and validation data must precede test data.

Use chronological splits:

```text
Earlier period → training
Later period   → validation
Latest period  → test
```

Do not randomly split event sequences when the goal is to simulate future deployment.

### 2.2 Authorization-time evaluation

A transaction must be scored using only signals available before or at authorization.

Do not use:

- Chargeback results.
- Confirmed fraud investigation.
- Future transactions.
- Future graph edges.
- Post-settlement information.
- Attack-family labels.
- Red-Team outcomes.
- Blue-Team decisions.

### 2.3 Attack-instance separation

Transactions from the same fraud campaign must not be split across train and test if doing so allows the model to memorize the campaign.

Use group-aware separation by:

```text
attack_instance_id
fraud_cluster_id
customer_id
beneficiary_id
device_id
```

### 2.4 Reproducibility

Every evaluation must record:

- Dataset version.
- Threat Library version.
- Simulator version.
- Compiler version.
- Feature version.
- Model version.
- Seed.
- Thresholds.
- Runtime environment.

---

## 3. Evaluation Layers

```text
Layer 1: Data quality
Layer 2: Synthetic-data fidelity
Layer 3: Transaction detection
Layer 4: Network detection
Layer 5: Agent and intent detection
Layer 6: Red-team robustness
Layer 7: Operational performance
Layer 8: Closed-loop improvement
```

---

## 4. Dataset Splits

### 4.1 Standard time split

```python
def time_split(df, train_ratio=0.70, validation_ratio=0.15):
    df = df.sort_values("timestamp").reset_index(drop=True)

    n = len(df)
    train_end = int(n * train_ratio)
    validation_end = int(
        n * (train_ratio + validation_ratio)
    )

    train = df.iloc[:train_end]
    validation = df.iloc[train_end:validation_end]
    test = df.iloc[validation_end:]

    return train, validation, test
```

### 4.2 Attack-family holdout

For novelty evaluation, hold out one attack family from training.

Example:

```text
Training:
- card-not-present
- mule network
- account takeover
- low-and-slow

Holdout:
- agent destination substitution
```

The Blue Team should be evaluated on:

1. Known attack families.
2. Mutated known attacks.
3. Held-out attack families.
4. Composite attacks.
5. Adaptive attacks.

### 4.3 Campaign-level split

All transactions from one attack instance must stay in one split.

```python
def group_split(df, group_column="attack_instance_id"):
    groups = df[group_column].dropna().unique()
    # Assign complete groups to train, validation, or test.
```

Do not place transactions from the same synthetic mule ring in both train and test.

---

## 5. Data Quality Metrics

Before evaluating the model, validate the data.

### 5.1 Structural validity

```text
Required-field completeness
Entity-reference validity
Timestamp validity
Currency validity
Positive amount validity
Transaction-state validity
Network-edge validity
Intent-before-payment validity
Agent-before-transaction validity
```

### 5.2 Label validity

```text
Legitimate rows have fraud label 0
Injected attack rows have fraud label 1
Attack family exists for simulated fraud
Ground truth is not used as a feature
```

### 5.3 Reproducibility

For a fixed seed:

```text
same rows
same attack IDs
same relationships
same labels
same metrics
```

---

## 6. Synthetic Transaction Fidelity

Synthetic attacks must resemble realistic payment data.

Do not evaluate only whether a classifier can distinguish real and synthetic data. A generator can fool a classifier while failing to preserve temporal or relational behavior.

Measure fidelity across:

```text
Marginal distributions
Conditional distributions
Temporal behavior
Customer behavior
Merchant behavior
Network structure
Fraud behavior
```

### 6.1 Marginal distribution fidelity

Compare:

- Amount.
- Currency.
- Payment rail.
- Merchant category.
- Authentication method.
- Hour of day.
- Day of week.
- Fraud prevalence.

Recommended metrics:

```text
Kolmogorov-Smirnov distance
Wasserstein distance
Jensen-Shannon divergence
Population Stability Index
```

### 6.2 Conditional fidelity

Compare distributions conditioned on:

```text
merchant category
payment rail
customer segment
country
fraud family
time period
```

Example:

```text
Amount distribution:
real fraud in electronics category
versus
synthetic fraud in electronics category
```

### 6.3 Temporal fidelity

Compare:

```text
inter-transaction time
transactions per customer per day
burst length
time between beneficiary creation and payment
login-to-payment time
fraud-event clustering
```

### 6.4 Behavioral fidelity

Compare:

```text
repeat merchant rate
new beneficiary rate
device reuse
IP reuse
customer amount deviation
transaction velocity
payment-rail switching
authentication changes
```

### 6.5 Fidelity report

```json
{
  "amount_ks": 0.08,
  "amount_wasserstein": 115.2,
  "hour_js_divergence": 0.04,
  "merchant_category_js_divergence": 0.06,
  "inter_event_time_wasserstein": 0.11,
  "repeat_merchant_difference": 0.02,
  "new_beneficiary_difference": 0.03,
  "valid_row_rate": 0.987,
  "fidelity_status": "pass"
}
```

---

## 7. Synthetic Network Fidelity

Evaluate generated networks separately from generated transactions.

### 7.1 Node statistics

Compare:

```text
node-type distribution
number of customers
number of accounts
number of devices
number of IP networks
number of merchants
number of beneficiaries
number of agents
```

### 7.2 Edge statistics

Compare:

```text
edge-type distribution
edges per account
accounts per device
accounts per IP
senders per beneficiary
customers per merchant
agents per tool
agents per merchant
```

### 7.3 Structural statistics

Compare:

```text
degree distribution
community-size distribution
clustering coefficient
modularity
connected-component sizes
fan-in and fan-out
path lengths
```

### 7.4 Fraud motifs

Measure the prevalence of motifs:

```text
many accounts → one beneficiary
many accounts → one device
many agents → one tool
merchant cluster → common settlement account
device → IP → account cluster
```

### 7.5 Network fidelity score

Use a documented weighted score:

\[
F_{\text{network}}
=
\sum_{k=1}^{K} w_kF_k
\]

where:

```text
sum(weights) = 1
```

Example:

```text
degree fidelity       0.25
edge-type fidelity    0.20
temporal fidelity     0.20
motif fidelity        0.20
community fidelity    0.15
```

Do not change weights after seeing the results.

---

## 8. Transaction-Level Detection Metrics

Fraud datasets are imbalanced, so accuracy is not sufficient. Precision-recall metrics are especially important when fraudulent transactions are rare. Scikit-learn defines average precision as a summary of precision across recall operating points. [272]

### 8.1 Required metrics

```text
Precision
Recall
F1
PR-AUC / Average Precision
ROC-AUC
False-positive rate
False-negative rate
Specificity
Balanced accuracy
Confusion matrix
```

### 8.2 Definitions

\[
\text{Precision}
=
\frac{TP}{TP+FP}
\]

\[
\text{Recall}
=
\frac{TP}{TP+FN}
\]

\[
F1
=
2\cdot
\frac{\text{Precision}\cdot\text{Recall}}
{\text{Precision}+\text{Recall}}
\]

\[
\text{FPR}
=
\frac{FP}{FP+TN}
\]

### 8.3 Recommended primary metrics

Use:

```text
Primary:
PR-AUC
Recall at fixed FPR
Precision at block threshold
F1 at selected operating point

Secondary:
ROC-AUC
Balanced accuracy
Calibration error
```

### 8.4 Python evaluation

```python
from sklearn.metrics import (
    average_precision_score,
    roc_auc_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
)

def evaluate_transaction_model(
    y_true,
    probabilities,
    threshold=0.75,
):
    predictions = (probabilities >= threshold).astype(int)

    tn, fp, fn, tp = confusion_matrix(
        y_true,
        predictions,
        labels=,[0][1]
    ).ravel()

    return {
        "pr_auc": float(
            average_precision_score(y_true, probabilities)
        ),
        "roc_auc": float(
            roc_auc_score(y_true, probabilities)
        ),
        "precision": float(
            precision_score(
                y_true,
                predictions,
                zero_division=0,
            )
        ),
        "recall": float(
            recall_score(
                y_true,
                predictions,
                zero_division=0,
            )
        ),
        "f1": float(
            f1_score(
                y_true,
                predictions,
                zero_division=0,
            )
        ),
        "false_positive_rate": float(
            fp / max(1, fp + tn)
        ),
        "false_negative_rate": float(
            fn / max(1, fn + tp)
        ),
        "confusion_matrix": {
            "tn": int(tn),
            "fp": int(fp),
            "fn": int(fn),
            "tp": int(tp),
        },
    }
```

---

## 9. Decision-Level Metrics

A fraud system usually has three actions:

```text
ALLOW
REVIEW
BLOCK
```

Evaluate each separately.

### 9.1 Allow rate

```text
number of approved transactions
/
total transactions
```

### 9.2 Review rate

```text
number of review transactions
/
total transactions
```

### 9.3 Block rate

```text
number of blocked transactions
/
total transactions
```

### 9.4 Correct action rate

Map risk and ground truth to the expected action.

Example:

```text
High-risk fraud → BLOCK
Medium-risk uncertain → REVIEW
Low-risk legitimate → ALLOW
```

Do not count every fraudulent transaction as requiring a block. Some may be appropriate for step-up or manual review.

---

## 10. Cost-Sensitive Evaluation

False positives and false negatives have different costs.

Define:

```python
COSTS = {
    "false_positive_block": 5,
    "false_negative_fraud": 100,
    "review": 2,
    "correct_allow": 0,
    "correct_block": 0,
}
```

Expected cost:

\[
C =
C_{FP}FP+
C_{FN}FN+
C_{R}R
\]

For simulated transactions, calculate:

```text
estimated_fraud_loss
estimated_prevented_loss
estimated_customer_friction
review_volume
```

The values are scenario assumptions, not real financial claims.

---

## 11. Probability Calibration

If the UI displays a probability, evaluate calibration.

### Metrics

```text
Brier score
Expected calibration error
Calibration curve
Reliability diagram
```

A score of `0.90` should mean approximately 90% risk within a comparable population—not merely a high ranking.

```python
from sklearn.metrics import brier_score_loss

brier = brier_score_loss(
    y_true,
    probabilities,
)
```

Use calibration data separate from model training.

---

## 12. Network-Level Detection Metrics

A network detector must not be evaluated only at transaction level.

### 12.1 Node-level metrics

For risky entities:

```text
account precision/recall
device precision/recall
beneficiary precision/recall
agent precision/recall
merchant precision/recall
```

### 12.2 Cluster-level metrics

```text
fraud-cluster precision
fraud-cluster recall
cluster F1
cluster detection delay
cluster purity
```

### 12.3 Edge-level metrics

For suspicious relationships:

```text
edge precision
edge recall
new-risky-edge detection
beneficiary-edge recall
agent-tool-edge recall
```

### 12.4 Campaign-level recall

A fraud campaign is successfully detected if:

```text
at least one high-value entity or relationship
is identified before simulated loss exceeds the threshold
```

Report:

```text
campaign detection rate
campaign detection delay
transactions detected per campaign
loss prevented per campaign
```

### 12.5 Network examples

```text
Mule network:
detect beneficiary cluster

Shared-device network:
detect suspicious device-account relationship

Agent network:
detect shared tool, timing, or destination structure
```

---

## 13. Agent and Intent Metrics

### 13.1 Intent-violation detection

Measure:

```text
amount violation recall
merchant violation recall
category violation recall
destination violation recall
currency violation recall
cumulative-spend violation recall
expired-intent detection
missing-intent detection
```

### 13.2 Agent identity metrics

```text
valid-agent acceptance rate
invalid-agent rejection rate
agent impersonation recall
credential-replay detection
agent attestation failure detection
```

### 13.3 Agent behavior metrics

```text
behavioral-drift recall
new-tool detection
out-of-scope action recall
agent-to-agent coordination detection
tool-provenance anomaly recall
```

### 13.4 Provenance completeness

Measure:

```text
percentage of payments with complete:
human → intent → agent → tool → merchant → transaction
```

---

## 14. Red-Team Attack Generation Metrics

### 14.1 Validity

```text
valid generated attacks
/
total generated attacks
```

A valid attack:

- Passes schema validation.
- Passes payment constraints.
- Passes temporal constraints.
- Passes network constraints.
- Passes agent and intent consistency.
- Passes safety checks.

### 14.2 Diversity

Measure diversity across:

```text
attack families
payment rails
merchant categories
customer profiles
network motifs
agent behaviors
intent violations
evasion strategies
```

Simple family coverage:

```python
family_coverage = (
    generated_families.intersection(target_families)
    / len(target_families)
)
```

### 14.3 Novelty

Calculate separately:

```text
semantic novelty
sequence novelty
network novelty
behavior novelty
agent/intent novelty
```

Do not use only embedding distance.

### 14.4 Attack success rate

```text
bypassed fraudulent attacks
/
valid generated fraudulent attacks
```

\[
ASR =
\frac{N_{\text{fraud missed}}}
{N_{\text{valid fraud generated}}}
\]

A lower ASR is better for the Blue Team.

### 14.5 Evasion quality

A successful attack must be:

```text
fraudulent
valid
realistic
low-scoring
impactful
non-duplicate
```

Do not reward an attack simply because it generates an impossible row with a low score.

---

## 15. Attack Fidelity Evaluation

For each generated attack, calculate:

```text
transaction fidelity
behavioral fidelity
temporal fidelity
network fidelity
agent/intent fidelity
```

### Attack fidelity score

```text
F_attack =
0.25 × transaction_fidelity
+ 0.20 × behavior_fidelity
+ 0.20 × temporal_fidelity
+ 0.20 × network_fidelity
+ 0.15 × agent_intent_fidelity
```

Report component scores separately.

### Fidelity categories

```text
A: 0.90–1.00
B: 0.75–0.89
C: 0.60–0.74
D: below 0.60
```

These grades are internal engineering labels.

---

## 16. Robustness Evaluation

Test the Blue Team against:

```text
known attacks
mutated attacks
composite attacks
held-out attack families
network variants
agent variants
low-and-slow variants
feature perturbations
```

### Robustness metrics

```text
robust recall
robust PR-AUC
bypass rate
performance degradation
adaptation time
attack-family coverage
false-positive change
```

### Robustness gap

\[
G_{\text{robustness}}
=
\text{Performance}_{\text{known}}
-
\text{Performance}_{\text{novel}}
\]

A smaller gap is better.

---

## 17. Adversarial Evaluation

The Red Team may optimize against a detector in simulation.

### Red-team objective

\[
J(a)=
\lambda_1 I(a)
+\lambda_2 F(a)
+\lambda_3 N(a)
-\lambda_4 R(a)
-\lambda_5 V(a)
\]

Where:

- \(I(a)\) = simulated financial impact.
- \(F(a)\) = realism/fidelity.
- \(N(a)\) = novelty.
- \(R(a)\) = detector risk score.
- \(V(a)\) = invalidity or safety penalty.

### Required constraints

```text
amount validity
timestamp validity
payment-rail validity
entity existence
network plausibility
intent consistency
agent permission constraints
simulation-only policy
```

NIST’s adversarial-machine-learning taxonomy distinguishes attacker goals such as evasion, poisoning, privacy attacks, and abuse, and emphasizes attacker knowledge, lifecycle stage, and mitigation. Use those categories to document your adversarial tests. [264][270]

---

## 18. Closed-Loop Evaluation

The closed loop contains two model versions:

```text
Blue model before retraining
Blue model after retraining
```

### Procedure

```text
1. Freeze model version A.
2. Generate valid attack set.
3. Score attacks using model A.
4. Record detected and missed attacks.
5. Create a Blue-Team failure report.
6. Convert validated misses to hard negatives.
7. Train model version B.
8. Evaluate model B on:
   - same attacks
   - mutated attacks
   - held-out attacks
   - legitimate controls
9. Compare performance.
```

### Required comparison

```text
attack bypass before
attack bypass after
PR-AUC before
PR-AUC after
recall before
recall after
F1 before
F1 after
false-positive rate before
false-positive rate after
```

### Improvement metrics

\[
\Delta ASR =
ASR_{\text{before}}
-
ASR_{\text{after}}
\]

\[
\Delta F1 =
F1_{\text{after}}
-
F1_{\text{before}}
\]

\[
\Delta Recall =
Recall_{\text{after}}
-
Recall_{\text{before}}
\]

A successful loop should reduce bypass without causing unacceptable false-positive growth.

---

## 19. Hard-Negative Training Rules

Only add an attack to hard-negative training when it:

```text
passes validation
passes realism checks
has reliable fraud ground truth
is not a duplicate
contains authorization-time features
has a recorded model decision
has an attack ID and seed
```

Do not train on:

```text
invalid rows
unvalidated LLM output
post-event labels as features
duplicate attacks
unrealistic adversarial examples
```

---

## 20. Held-Out Evaluation

Maintain an evaluation set that is never used for hard-negative retraining.

```text
Training:
historical attacks + selected hard negatives

Validation:
threshold and model selection

Held-out test:
unseen attack instances and selected unseen families
```

The held-out set should include:

```text
legitimate behavior
known fraud
mutated fraud
composite fraud
network attacks
agent/intent attacks
```

---

## 21. Model Comparison

Compare models on identical splits and features.

```text
Model A: Logistic Regression
Model B: Random Forest
Model C: LightGBM
Model D: XGBoost
Model E: Autoencoder + classifier
Model F: LightGBM + graph features
Model G: Hybrid transaction + graph + intent
```

### Required comparison table

| Model | PR-AUC | Recall | Precision | F1 | FPR | p95 latency | Explainability |
|---|---:|---:|---:|---:|---:|---:|---|
| Logistic Regression | | | | | | | High |
| Random Forest | | | | | | | Medium |
| LightGBM | | | | | | | High |
| XGBoost | | | | | | | High |
| Hybrid | | | | | | | High |

---

## 22. Ablation Testing

Remove signal groups one at a time.

```text
Full model
- network features
- intent features
- agent features
- behavior features
- device features
- identity features
```

Measure the change in:

```text
PR-AUC
Recall
F1
False-positive rate
Novel-attack recall
Agent-attack recall
Network-campaign recall
```

Example:

| Feature group removed | PR-AUC change | Novel recall change | Interpretation |
|---|---:|---:|---|
| Network | | | Network value |
| Intent | | | Agentic-payment value |
| Device | | | Account-takeover value |
| Behavior | | | Baseline behavior value |

This shows judges which part of the architecture actually contributes.

---

## 23. Explainability Evaluation

A decision explanation must:

```text
reference available features
identify the main risk factors
match model behavior
avoid fabricated evidence
recommend a plausible action
```

### Explanation metrics

```text
reason-code validity
feature-to-reason mapping accuracy
explanation consistency
top-feature overlap with SHAP
analyst usefulness
```

### Example

```text
Technical feature:
beneficiary_sender_count_7d = 12

Reason code:
Beneficiary received payments from many accounts recently.
```

Do not let a language model invent a reason that was not present in the data.

---

## 24. Operational Metrics

### Latency

Measure:

```text
p50 latency
p95 latency
p99 latency
```

Measure separately:

```text
feature construction
transaction model
network features
intent policy
agent scoring
explanation generation
```

The LLM explanation should not block the authorization decision.

### Throughput

```text
transactions scored per second
events processed per second
network updates per second
```

### Reliability

```text
successful requests
timeouts
model errors
fallback decisions
missing-feature rate
```

### Fallback behavior

If a component fails:

```text
ML unavailable → deterministic safe policy
graph unavailable → transaction model plus conservative review
LLM unavailable → template-based explanation
```

---

## 25. Threshold Selection

Use the validation set to select thresholds.

```python
def decide(probability, review_threshold, block_threshold):
    if probability >= block_threshold:
        return "BLOCK"

    if probability >= review_threshold:
        return "REVIEW"

    return "ALLOW"
```

Select thresholds using:

```text
target recall
maximum false-positive rate
expected loss
review capacity
customer friction
```

Do not select thresholds on the final test set.

---

## 26. Calibration Evaluation

If the frontend displays risk as a probability, measure:

```text
Brier score
Expected calibration error
Calibration curve
```

A model may rank transactions well but produce poorly calibrated probabilities.

The system should distinguish:

```text
risk score
fraud probability
policy severity
```

These are not automatically identical.

---

## 27. Recommended P0 Evaluation

For P0, implement only:

```text
time-based split
PR-AUC
ROC-AUC
precision
recall
F1
false-positive rate
confusion matrix
threshold policy
amount fidelity
basic temporal fidelity
inference latency
reproducibility
```

P0 should not yet require:

```text
GNN metrics
agent-to-agent metrics
advanced novelty metrics
adaptive attack optimization
```

---

## 28. Recommended P1 Evaluation

Add:

```text
network fidelity
network cluster recall
beneficiary concentration detection
shared-device detection
attack-family coverage
mutation diversity
candidate novelty
```

---

## 29. Recommended P2/P3 Evaluation

Add:

```text
intent violation recall
agent identity detection
tool-provenance detection
behavioral drift
agent-network detection
composite attack recall
```

---

## 30. Recommended P4/P5 Evaluation

Add:

```text
adaptive attack success
robustness gap
hard-negative improvement
held-out attack performance
closed-loop bypass reduction
model degradation under mutation
```

---

## 31. Final KPI Dashboard

The Command Center should show:

```text
Transaction PR-AUC
Fraud recall
False-positive rate
Attack bypass rate
Held-out attack recall
Network campaign recall
Intent violation recall
Attack fidelity
Attack diversity
p95 detection latency
Before/after closed-loop improvement
```

Recommended judge-facing metrics:

```text
Attack bypass before: 31%
Attack bypass after: 8%
Held-out attack recall: 72%
Network campaign recall: 84%
Intent violation recall: 91%
Synthetic validity rate: 97%
p95 authorization scoring: 42 ms
```

Only display values produced by your actual run. Never hard-code example numbers.

---

## 32. Evaluation Report

Every run must produce:

```json
{
  "run_id": "RUN-0001",
  "model_version": "BLUE-0.1.0",
  "threat_library_version": "0.1.0",

  "transaction_metrics": {
    "pr_auc": 0.86,
    "roc_auc": 0.94,
    "precision": 0.81,
    "recall": 0.74,
    "f1": 0.77,
    "false_positive_rate": 0.021
  },

  "generation_metrics": {
    "validity_rate": 0.987,
    "diversity_score": 0.73,
    "candidate_novelty": 0.68,
    "attack_success_rate": 0.31,
    "transaction_fidelity": 0.88,
    "network_fidelity": 0.81
  },

  "agent_metrics": {
    "intent_violation_recall": 0.91,
    "destination_mismatch_recall": 0.89,
    "agent_drift_recall": 0.66
  },

  "operational_metrics": {
    "p50_latency_ms": 18.4,
    "p95_latency_ms": 42.0,
    "throughput_per_second": 615
  },

  "closed_loop": {
    "attack_success_before": 0.31,
    "attack_success_after": null,
    "f1_before": 0.77,
    "f1_after": null
  }
}
```

---

## 33. Definition of Done

The evaluation framework is complete when it can:

1. Split data chronologically.
2. Prevent attack-instance leakage.
3. Evaluate transaction detection.
4. Evaluate decisions at multiple thresholds.
5. Evaluate synthetic transaction fidelity.
6. Evaluate synthetic network fidelity.
7. Evaluate attack diversity.
8. Evaluate candidate novelty.
9. Measure Red-Team bypass rate.
10. Measure network campaign detection.
11. Measure intent and agent detection.
12. Measure latency and throughput.
13. Produce explanations and reason-code checks.
14. Compare model versions.
15. Run before/after closed-loop evaluation.
16. Generate a reproducible evaluation report.

---

## 34. Final Evaluation Principle

The strongest system is not the one with the highest offline AUC.

The strongest system is the one that can demonstrate:

```text
Realistic attack generation
        ↓
Strong transaction detection
        ↓
Network-level correlation
        ↓
Agent and intent verification
        ↓
Explainable intervention
        ↓
Measured bypass
        ↓
Hard-negative learning
        ↓
Lower bypass on the next attack round
```

The final success criterion is:

\[
\text{Blue-Team Improvement}
=
\text{Lower Attack Bypass}
+
\text{Stable False-Positive Rate}
+
\text{Improved Held-Out Recall}
\]

The Red Team must become harder to detect without becoming unrealistic. The Blue Team must become stronger without blocking legitimate payment behavior.
```



