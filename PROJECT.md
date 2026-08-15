# FraudForge

FraudForge is a **closed-loop payment-fraud system**. It finds emerging GenAI-powered attack families, turns them into synthetic transactions, scores those rows with a hybrid detector, and retrains on what slipped through.

It is built for **Mastercard-style payment rails**: card-not-present spend, UPI / authorized push, agent checkout, and the first payments after a KYC or login event. The console uses Mastercard red (`#EB001B`), black, and white.

This is a **defensive lab**. It does not send live payments, write phishing emails, generate fake ID images, or clone voices.

---

## What the project does

Payment fraud changes faster than a static rules file. FraudForge treats detection as a red team / blue team loop:

```
Identify  →  Generate  →  Defend  →  Measure  →  Retrain  →  Repeat
```

| Step | Role | What you get |
| --- | --- | --- |
| **Identify** | Research agent + threat-intel catalog | Distinct attack families (identity, authentication, agent pay, UPI, and more) |
| **Generate** | Synthetic attack generator | Tabular fraud rows from a legitimate seed + family overlay |
| **Defend** | Hybrid classifier | BLOCK or APPROVE with rules, tree, graph, and intent layers |
| **Closed loop** | Adversarial feedback | Attack success before vs after retrain |
| **Real-time** | FastAPI `/detect` | Batch scoring with measured latency |
| **Novelty** | Hold-out / washed rows | Coverage of attacks the first model did not train on |

The working dataset is the **ULB credit-card table** (`Time`, `V1`–`V28`, `Amount`, `Class`). Readable fraud signals are overlaid on top so analysts can see *why* a row was blocked.

---

## Why Mastercard

Mastercard sits at the intersection of **network payments, identity, and agentic commerce**:

- Public Mastercard work on **AI in fraud prevention** and **threat intelligence** frames the problem: GenAI raises both attack velocity and detection quality.
- **Agent Pay** adds a delegation layer — a human authorizes an agent within amount, merchant, and time limits. A new fraud signal is *intent mismatch*: the executed payment is not what the user signed.
- Identity and authentication attacks (synthetic IDs, deepfake KYC, voice clones) show up on the network as **the first payments after onboarding or login**, not as video files inside this prototype.

FraudForge maps those ideas onto a detector you can run locally: catalog the family, simulate the payment aftermath, score it, then feed misses back into training.

---

## Attack families

The catalog has **30+ families**. Some are **simulatable** (synthetic rows + training). Others are **identified only** (named from intel, not yet turned into a row overlay).

### Identity fraud

| Attack | Family | What we simulate | What we do not generate |
| --- | --- | --- | --- |
| Synthetic identity | `synthetic_identity` | New device, document-tamper score, mule spend | GAN faces, fake credit files |
| Deepfake KYC | `deepfake_kyc` | Liveness risk + biometric mismatch on first payments | Injected video |
| Document forgery | `document_forgery` | High document-tamper score | Fake passports or licenses |
| Face swap | `face_swap` | Biometric mismatch after video KYC | Real-time face-swap video |
| Voice clone (login) | `voice_clone_auth` | Voiceprint mismatch, then card-not-present spend | Cloned audio |

### Authentication fraud

| Attack | Family | What we simulate | What we do not generate |
| --- | --- | --- | --- |
| AI-generated phishing | `phishing_ato` | New device, location jump, velocity | Phishing email or SMS copy |
| Voice impersonation | `voice_impersonation` | Voiceprint miss + mule beneficiary | Family / executive voice audio |
| Deepfake video call | `deepfake_video` | Weak biometric overlay (low feasibility) | Support-call deepfakes |
| Multilingual scam automation | `multilingual_scam` | Cross-border authorized push to a mule | Translated lure text |

### Payment and agent families (also in the product)

Phishing ATO, deepfake UPI collect, malicious agent / intent mismatch, authorized push, QR swap, prompt-injection destination change, credential stuffing, and related catalog entries.

**Flagship demo:** an AI shopping agent is steered to change the *destination* of a laptop purchase. Amount-only scoring would APPROVE. The intent engine BLOCKs because the payee is not on the signed list. Settlement is simulated and prevented — no live rail.

---

## How detection works

A row is scored in four layers. **BLOCK if the tree fires or the intent rule fires.** Weak behavioral rules add score only; they never block alone.

| Layer | Signal | Example |
| --- | --- | --- |
| Rules | Device, velocity, location, KYC/auth flags | New device + location mismatch |
| Tree (ML) | HistGradientBoosting / XGBoost on PCA + overlay | Trained on real fraud + synthetic family rows |
| Graph | Mule / shared-payee risk | High `mule_account_risk` |
| Intent | Signed constraint vs executed payment | `constraint_violation` or amount over limit |

Identity and authentication families add four overlay fields:

- `kyc_liveness_risk`
- `document_tamper_score`
- `biometric_mismatch`
- `voiceprint_mismatch`

Legitimate rows draw near-zero values. Attack rows draw from the family template. The detector is trained on those synthetic overlays so a KYC-style row can BLOCK even when the PCA signature looks ordinary.

---

## Console (Streamlit)

| Page | Purpose |
| --- | --- |
| System flow | End-to-end picture of the loop |
| Payment simulator | Event timeline, weak vs full policy, settlement prevented |
| Red team | Mutate a legitimate row into a named attack family |
| Blue team | Score that row and show layer breakdown |
| Identify | Threat intel → ranked families |
| Generate | Synthetic rows, fidelity (KS / Wasserstein), attack success |
| Defend | Classifier metrics, scenarios, SHAP-style explanations |
| Closed-loop evaluation | Attack success and F1 before vs after retrain |

---

## Stack

| Piece | Choice |
| --- | --- |
| API | FastAPI (`backend/app.py`) |
| UI | Streamlit (`frontend/app.py`) |
| Detector | XGBoost when OpenMP is available; otherwise HistGradientBoosting |
| Synthesizer | CTGAN / Torch GAN, with bootstrap fallback |
| Research | NVIDIA or OpenAI if a key is set; otherwise catalog ranker |
| Data | ULB credit-card CSV + narrative overlay |
| Store | SQLite + JSONL simulation events |

---

## Run locally

```bash
unset DYLD_LIBRARY_PATH          # macOS: avoids a broken numpy/OpenMP mix
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env             # optional NVIDIA_API_KEY or OPENAI_API_KEY

python scripts/train_all.py      # data + models + demo artifacts

# Terminal 1
uvicorn backend.app:app --reload --port 8000

# Terminal 2
streamlit run frontend/app.py
```

On macOS, XGBoost needs OpenMP (`brew install libomp`). Without it the detector still trains.

Tests:

```bash
unset DYLD_LIBRARY_PATH
source .venv/bin/activate
python -m pytest tests -q
```

---

## API (selected)

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | Liveness |
| GET | `/research/catalog` | Attack catalog |
| POST | `/research/hypotheses` | Identify |
| POST | `/attacks/generate` | Generate synthetic rows |
| POST | `/detect` | Batch score |
| POST | `/evaluate/loop` | Closed-loop metrics |
| POST | `/simulation/start` | Payment simulator |
| POST | `/simulation/flagship` | Agent destination-substitution demo |

---

## Safety

- No live card, UPI, or wallet execution
- No phishing copy, malware, or exploit payloads
- No stolen credentials or contact with victims
- Synthetic data and simulated settlement only
- Threat-intel notes are paraphrased public sources (Mastercard, OWASP, UPI / network write-ups)

---

## Repository map

```
backend/                 API, agents, overlays, simulation, policy
backend/attack_catalog.py  Family catalog (identify + simulatable flags)
backend/features.py        Overlay templates and training mix
frontend/app.py            Streamlit console
scripts/                   Download data and train models
tests/                     Pytest coverage
```
