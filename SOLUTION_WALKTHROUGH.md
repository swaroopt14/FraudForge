# FraudForge solution walkthrough

Mastercard Innovation Challenge 2026 — Identify / Generate / Defend as a closed red/blue loop.

## Why this architecture

Payment fraud shifts faster than a static classifier. FraudForge treats detection as an adversarial process: a red team proposes attack families from threat intel, synthesizes tabular attacks, and searches for evasions; a blue team scores with XGBoost, explains with SHAP, flags novelty with an autoencoder, then retrains on hold-out failures.

The working table is the ULB credit-card set (284,807 rows, 0.17% fraud). IEEE-CIS is too wide for a live CTGAN fit. A small **narrative overlay** (`device_new`, `velocity_1h`, `location_mismatch`, `beneficiary_name_match`, `mule_account_risk`, `constraint_violation`, `amount_vs_limit_ratio`, `hour_of_day`) maps judge scenarios onto readable SHAP features without inventing IEEE-CIS columns.

## Pillar mapping

| Criterion | Where it lives |
| --- | --- |
| Diversity of attacks | Five families from the research agent: phishing ATO, deepfake collect, malicious agent, synthetic identity, authorized push |
| Fidelity of simulation | `CTGANSynthesizer` on real fraud rows; KS on `Amount` / `V14` / `Time` in the generation view |
| Detection efficacy | XGBoost with `scale_pos_weight ≈ neg/pos` and a validation-tuned threshold. Target: F1 > 0.80, ROC-AUC > 0.90, FPR < 1% |
| Novelty | Closed loop on **hold-out** adversarial / novel rows (not the same rows used to retrain) |
| Real-world feasibility | XGBoost inference, SQLite, Streamlit, FastAPI; no live DQN in the judging path |

## Agents

**Red team**

1. `FraudResearchAgent` — LangChain ChatOpenAI / ChatAnthropic JSON hypotheses; canned fallback if no API key.
2. `AttackGenerator` — SDV CTGAN; bootstrap+noise if the synthesizer is missing.
3. `AdversarialOptimizer` — evolutionary ±10% search on Amount, V-features, and narrative flags (DQN+Box in the brief is invalid; this stays off the live critical path).

**Blue team**

1. `FraudDetector` — XGBoost + SHAP `TreeExplainer`.
2. `AnomalyDetector` — autoencoder on legitimate subsample; 95th-percentile reconstruction threshold.

**Loop**

1. `EvaluationAgent` — attack success (score < threshold), mixed-set F1, FPR.
2. `FeedbackAgent` — feature-mean gap between bypassed and detected, then three new hypotheses.

## Four judge scenarios

1. **AI phishing → ATO** — high Amount, `device_new=1`, velocity spike, `location_mismatch=1` → BLOCK. SHAP should surface those overlay features.
2. **Deepfake voice → collect / mule** — `beneficiary_name_match=0`, high `mule_account_risk` → BLOCK or delay.
3. **Malicious agent** — `constraint_violation=1`, `amount_vs_limit_ratio > 1` → BLOCK.
4. **Closed loop** — precomputed `closed_loop.json`: attack success drops after retrain; mixed F1 rises. Optional live recompute.

Threat-intel prompts for 1–3 are on the Attack discovery view; matching transactions are on Fraud detection.

## Closed-loop protocol

- Generate novel high-amount rows on a legitimate PCA signature, plus CTGAN samples, then adversarially wash risk flags.
- Split train attacks vs **hold-out** attacks.
- Score hold-out with the production detector (before).
- Retrain on original train split + train attacks.
- Score the same hold-out (after).
- Mixed test = original hold-out transactions + hold-out attacks, so F1 lift is not self-scoring.

## What we did not copy from the brief

- Deprecated `langchain.LLMChain` / `sdv.tabular.CTGAN`.
- DQN on a continuous `Box` action space.
- Training CTGAN on 871 IEEE-CIS columns during a demo.
- Working phishing copy or exploit payloads — hypotheses are defensive summaries only.

On this machine, OpenMP (`libomp`) was not available, so the shipped detector uses sklearn `HistGradientBoostingClassifier` with the same depth/trees recipe. Install `libomp` and retrain to use native XGBoost. Synthetic fraud uses a bootstrap sampler when SDV/Torch are not installed; `AttackGenerator` still prefers SDV CTGAN, then a Torch GAN, then bootstrap.
