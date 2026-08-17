# Authorization Intelligence — post-P plan

**Status:** parked. Do not implement until the remaining P backlog is done.  
**Product name in UI:** Authorization Intelligence (never issuer/network brand names).  
**Reference systems:** Visa Advanced Authorization (VAA) and Mastercard Decision Intelligence (DI). We are matching *capabilities*, not cloning their models, data, or SLA.

**Research (what they actually do and which parameters are public):** `docs/research/VAA_AND_DECISION_INTELLIGENCE.md`

This note is the target after P0–Pn. Current lab scoring stays frozen until then.

---

## What those systems actually do

| Capability | VAA (authorization-time) | Decision Intelligence | Lab analogue |
|---|---|---|---|
| When it runs | At authorization, before the issuer decision | At authorization, with cardholder context | `POST /transactions/score` plus a new fast path |
| Inputs | Hundreds of risk elements in one pass | Historical behavior vs current device/session | Expand beyond the 15 `FEATURE_COLUMNS` |
| Speed | ~1 ms score | Fast score + contextual story | Two-speed: hot path ≤5 ms, warm path for STEP_UP/REVIEW |
| Device | Device age / fingerprint | Current device vs known profile | `device_age_days` already exists; add profile match |
| Location | IP / distance from home | Travel-aware: unusual location can still be legitimate | `distance_from_home` exists; add travel/context, not a hard block |
| Merchant | Merchant category / MCC risk | Merchant in the cardholder’s pattern | `merchant_risk` exists; add MCC + habitual merchants |
| Output | Risk score | Score + “why this still looks like the customer” | Score + policy + compact reasons + optional narrative |

The important DI idea: **anomaly ≠ fraud**. A transaction from a new city can be travel. A new device on the home IP can be a phone upgrade. The model must score *relationship to history*, not only “is this rare.”

---

## What FraudForge already has (do not rebuild)

From P0:

- 15 tabular features, including `device_age_days`, `distance_from_home`, `merchant_risk`, velocity windows, `account_age_days`
- Blue Team: Logistic Regression + LightGBM (or HistGradientBoosting fallback)
- Policy: `ALLOW / STEP_UP / REVIEW / BLOCK` from `fraud_probability` (probability is not the decision)
- SHAP (or coefficient fallback) for top drivers
- Red Team attack families to stress the detector

Frontend already has Blue Team pages (including Network). Those stay empty/honest until the matching backend exists.

---

## Why we wait until remaining P work is done

Authorization Intelligence sits **on top of** the P stack, not beside it.

| Finish first | Why Intelligence needs it |
|---|---|
| P1 — calibrated scores, honest empty states, no invented IDs/SLOs | Hot-path score must be a real model output |
| P2 — network / geo / device / IP / beneficiary graph features (no GNN required) | These *are* the extra VAA-style risk elements |
| Later P — behavioral windows, intent/agent signals, closed-loop retrain | DI-style “this looks like this customer” needs history |
| Red Team travel / device-upgrade / merchant-habit scenarios | You cannot claim travel-aware detection without attacks that look like travel |

If we build Intelligence now, it will fake context from the same 15 columns and look like a demo overlay. After P, the same UI can show real features.

---

## Architecture (two speeds)

Do **not** put a generative model on the authorization hot path. VAA’s 1 ms budget is a gradient-boosted / rules ensemble over precomputed features, not an LLM.

```
authorization request
        │
        ▼
┌───────────────────────┐
│  Profile store        │  rolling features for customer / device / merchant
│  (precomputed)        │
└───────────┬───────────┘
            ▼
┌───────────────────────┐
│  HOT PATH  (≤ 5 ms)   │  LightGBM / XGBoost over 80–200 risk elements
│  Authorization score  │  + small calibrated rules (travel, device match)
│  Policy band          │  ALLOW / STEP_UP / REVIEW / BLOCK
│  Top-k drivers        │  precomputed gain or TreeSHAP on a tiny window
└───────────┬───────────┘
            │
            ├── ALLOW / BLOCK → return immediately
            └── STEP_UP / REVIEW → WARM PATH (50–300 ms, not 1 ms)
                    │
                    ▼
            ┌───────────────────────┐
            │  Contextual reasoner  │  small generative or template+RAG
            │  “history vs now”     │  only for analyst / step-up copy
            └───────────────────────┘
```

**Hot path** matches VAA: many features, one score, milliseconds.  
**Warm path** matches the *explainable* part of DI: “this merchant is new, but device and spend pattern match last year’s trip.” Judges see the narrative; authorization latency stays honest.

---

## Feature plan (hundreds of risk elements, lab-scale)

Group features so we can grow without a 871-column IEEE dump. Target **80–200** lab features, not 400 production secrets we do not have.

1. **Transaction** — amount, hour, MCC, channel, currency (you have a subset)
2. **Velocity** — 1h / 24h / 7d counts and amounts (you have 1h/24h)
3. **Device** — age, first-seen, match-to-profile, OS/browser hash stability
4. **Geo / IP** — distance from home, distance from last txn, country change, travel corridor
5. **Merchant** — category risk, habitual merchant flag, MCC novelty
6. **Beneficiary** — new payee, concentration, graph degree (P2)
7. **Network** — shared device/IP/beneficiary clusters (P2)
8. **History match** — cosine / rank of “current vector vs 30d customer centroid”
9. **Travel context** — `likely_travel` from geo sequence (airport MCC + city hop + prior trips)
10. **Auth / session** — failed auth, step-up history (ATO already raises `failed_auth_count`)

`FEATURE_COLUMNS` stays frozen for P0 models. Intelligence gets `FEATURE_COLUMNS_AUTH` (or V030) with its own model version, same leakage rules: no `attack_family`, no `fraud_label` in X.

---

## Models (how to actually “match” them)

### Hot-path scorer (VAA analogue)

- Gradient boosting on `FEATURE_COLUMNS_AUTH`
- Optional tiny rule overlay:
  - `likely_travel=1` **lowers** geo-anomaly contribution (do not auto-BLOCK on distance)
  - `device_match=1` **lowers** new-location contribution
  - `new_device AND new_beneficiary AND velocity_spike` **raises** score
- Calibrated probability → existing policy bands
- Measure p50/p95 latency in `evaluation/benchmarks/auth/` — target **p95 &lt; 10 ms** on one CPU for a single row; 1 ms is a stretch goal after feature precompute, not a fake default

### Context model (DI analogue)

Not a GNN. Not an LLM in the 1 ms path.

- Customer profile vector: median amount, usual hours, usual MCCs, usual cities, known devices
- Score `context_fit = similarity(current, profile)`
- Combine: `final = combine(fraud_model, 1 - context_fit)` with travel discount
- Warm path: retrieve last N events + profile → **templated** narrative first; optional small LLM only if `AUTH_NARRATIVE=1` and decision is STEP_UP/REVIEW

Example narrative (lab copy, no issuer brands):

> Device matches a known phone. Distance from home is high, but MCC and amount sit inside this customer’s travel pattern. Beneficiary is new — step-up, do not block.

---

## Red Team scenarios that prove it (required)

Without these, the feature is a scoreboard, not Intelligence.

| Scenario | Looks like | Correct Blue action |
|---|---|---|
| `travel_legit` | New city, known device, habitual spend | ALLOW or low STEP_UP |
| `ato_travel_cover` | New city + new device + new beneficiary | REVIEW/BLOCK |
| `device_upgrade` | New device, home IP, same merchants | ALLOW |
| `merchant_habit_break` | Known device, first-time high-risk MCC | STEP_UP |
| `low_and_slow` (existing) | Still must detect | REVIEW/BLOCK |

Acceptance: `travel_legit` must **not** inherit the same score as `ato_travel_cover` just because `distance_from_home` is large.

---

## API / UI (after P)

Keep current `/transactions/score`. Add a versioned payload, do not break P0 clients.

```json
{
  "fraud_probability": 0.22,
  "auth_score": 221,
  "policy": "ALLOW",
  "latency_ms": 3.4,
  "drivers": [{"feature": "device_match", "direction": "protective"}],
  "context": {
    "history_fit": 0.81,
    "likely_travel": true,
    "device_match": true
  },
  "narrative": null
}
```

`narrative` is null on ALLOW/BLOCK hot path. Filled only on STEP_UP/REVIEW.

UI: Blue Team → **Authorization Intelligence** (not “VAA”, not issuer names). Show score, drivers, context chips (Travel / Known device / New payee), latency. Evaluation page: P0 model vs Auth model on travel vs ATO.

---

## Honest limits (say this in the demo)

- We will not have hundreds of proprietary issuer signals or a global 1 ms fabric.
- We will have a **lab-faithful analogue**: many risk elements, millisecond-class boosting, travel-aware context, explanations.
- Generative AI is for **context text and Red Team generation**, not for the authorization number.
- Closed-loop retrain still comes from Red Team failures, not from copying a network’s production weights.

---

## Implementation order (when P is done)

1. Freeze P0/P1/P2 model hashes. Auth work is a new version (`BLUE-AUTH-0.1.0`).
2. Profile store: per-customer rolling stats from IEEE + synthetic legit.
3. `FEATURE_COLUMNS_AUTH` + attach functions (geo sequence, device match, travel flag, history_fit).
4. Train booster. Latency harness. Calibrate. Policy unchanged unless travel overlay needs it.
5. Red Team travel / upgrade / habit-break generators + tests.
6. Warm-path templates; optional LLM narrative behind a flag.
7. UI + evaluation table: “same distance_from_home, different context → different decision.”
8. Demo script: one travel ALLOW, one ATO BLOCK, both in &lt;10 ms for the score.

---

## Definition of done (match the pitch)

A judge can say:

1. The lab scores many risk elements at once (not 15 only).
2. The score returns in a few milliseconds, measured, not hardcoded.
3. A traveling customer with a known device is not treated like fraud.
4. A new device + new payee + geo jump is treated like fraud.
5. STEP_UP/REVIEW shows a short “history vs now” reason.
6. No issuer/network brand names in the product UI.
7. P0 models still load and compare; Auth is an additive version.

Until then, keep shipping P items. This file is the backlog item to pick up after.
