# Research: VAA and Decision Intelligence

**Audience:** FraudForge, after remaining P work.  
**Product UI:** never use issuer/network brand names. This file is internal research.  
**Updated:** 2026-08-17.

Neither company publishes the full internal feature list. What follows is **only what they state publicly**, plus the **authorization-message fields every such scorer sits on**, plus **inferred families** (clearly marked). Do not treat inferred rows as official specs.

---

## 1. Where they sit in the payment flow

Both run **in-flight at authorization**, on the network, before the issuing bank’s yes/no.

```
cardholder → merchant/acquirer → CARD NETWORK (score here) → issuer decision → response
```

Important: **they do not approve or decline**. They attach a risk score (and often reason codes) to the authorization. The **issuer** decides ALLOW / DECLINE / step-up, often using the network score plus their own rules (Visa Risk Manager, issuer fraud engine).

That is the same split as FraudForge: model probability ≠ policy decision.

---

## 2. Visa Advanced Authorization (VAA)

### What it is

A real-time fraud **risk score** on VisaNet (now also sold network-agnostic under Visa Protect). Historically neural-network based; Visa now markets it as machine-learning / AI on the Visa AI platform.

Sister products:

| Product | Role |
|---|---|
| **VAA** | In-flight score for card payments (Visa and, in Protect, non-Visa) |
| **Visa Risk Manager (VRM)** | Issuer UI: rules using the VAA score **plus 70+ transaction parameters** |
| **Visa Deep Authorization (VDA)** | Separate **deep-learning RNN** score for **card-not-present**, sequential account + merchant context |

VDA is closer to “history as a sequence” than classic VAA. Do not mix the two in the demo.

### Official numbers (marketing, not a lab SLA)

| Claim | Source |
|---|---|
| ~**1 millisecond** per transaction | Visa 2019 press; AU 2019 press |
| **100%** of VisaNet authorizations scored | Same |
| **400 unique attributes** (current Protect page) vs **500+** (2019 press / EU case study) | Visa pages disagree; treat as “hundreds” |
| Up to **2 years** of account history in the profile | Visa UK Risk Essentials; EU case study |
| ~**65,000** scores/sec (case-study figure) | Visa EU VAA case study |
| Score shared with the issuer for approve / decline / follow-up | Visa 2019 press |

### Score

Industry write-ups of VAA describe a **1–99** risk score (**1 = least risky, 99 = most risky**). Visa’s current marketing page says only “a simple-to-use risk score,” not the numeric range. Treat 1–99 as **widely reported, not a published API spec**.

### What they say they look at (named examples)

From Visa’s 2019 technical explanation (PaymentsJournal summary of Visa’s own description):

- Transaction **type** (in-store vs online)
- **Entry mode** (contactless vs chip vs CNP)
- Whether this **account has been used at this merchant before**
- **Time of day**
- **Amount**
- Ability to still call a txn **good** for a **new or infrequent shopper** (false-decline control)

From current Visa Protect copy:

- Fraud patterns by **location of issuance**, **card type**, **transaction type**
- **Global** VisaNet view, not only this issuer’s book

VRM (rules on top of VAA) uses the score plus **70+ parameters** issuers can rule on. Those 70+ are **not** the 400 model features; they are the **levers the bank sees**.

### What they do *not* publish

The 400–500 **model attributes** (derived velocities, embeddings, graph degrees, etc.) are proprietary. Anyone listing “device age, IP distance from home, MCC” as *the* VAA spec is reconstructing typical authorization-risk families, not quoting a Visa data dictionary.

---

## 3. Decision Intelligence (DI) and DI Pro

### What it is

A **transaction risk monitoring** product: one score into the issuer authorization flow, plus reason codes / insights. Marketed as scoring **any network**, not only this brand’s rails.

**DI Pro** (announced Feb 2024) adds:

- **Generative AI techniques** (not “ChatGPT declines the payment”)
- **Graphing algorithms** — relationships among cardholder, merchant, and other entities
- Scan of **~1 trillion data points** (marketing scale of the graph/feature space)
- Pro layer said to improve the DI score in **&lt; 50 ms**
- Claimed **~20%** average fraud-detection lift (up to **300%** in some modelling); **&gt;85%** false-positive reduction in their analysis

Johan Gerber (Mastercard security) has described the core model as an **RNN “inverse recommender”**: *given this cardholder’s history, would we have recommended this merchant, this way, right now?* If not, risk rises. That is **pattern completion / relationship**, not a static rule like `distance_from_home > X`.

Latency context:

- **Pro enhancement:** &lt; 50 ms (official press)
- **Full authorization path** (orchestration + network + bank): often discussed as **&lt; 300 ms** end-to-end — that is the *payment* budget, not the model-only budget

### Official input families (named)

Feb 2024 press: DI already analyzed, in real time:

- **Account** information
- **Purchase** information
- **Merchant** information
- **Device** information

Product page adds:

- **Transaction context**
- **Cardholder behavior**
- **Merchant relationships** (not only “have they been at this one merchant”)
- Real spending behavior **even if the merchant is new to this cardholder** (graph: similar merchants / similar people)

Episode Six (implementation partner) lists issuer-facing outputs:

- Risk score **in the authorization message**
- Cardholder- and transaction-level **insights**
- **Reason codes** to contextualize risk
- Custom **rules** on top

### Score

No public, stable “DI = 0–999” spec on the product page. Related Mastercard risk products use integer scores (higher = more risk) and concatenated score+reason (e.g. Expert Monitoring Solutions examples like `843` + reason `09`). **Do not copy a fake 0–999 into FraudForge as “the DI scale.”** Use our own calibrated probability + policy bands.

### Identity Insights (related, not DI)

Mastercard **Identity Insights for Accounts** *does* publish a data dictionary. It is a **digital-identity** product, not the authorization RNN, but it shows which **device/IP/email** parameters this company actually computes:

| Parameter | Meaning |
|---|---|
| Identity risk score | Combined identity network score (documented 0–500 bands) |
| Email / phone / address validity and match-to-name | KYC-ish linkage |
| Email first-seen days, domain age | Synthetic identity |
| IP risk, proxy class, last-seen, geolocation | VPN / location |
| IP–phone distance, IP–address distance | “Home vs this session” |
| Device risk score, type, platform, browser | Device intelligence |
| Browser vs IP timezone mismatch | Spoof / travel signal |
| Device+email+phone first-seen together | New combo vs old combo |

Those are the closest **public parameter names** for “device vs history.”

---

## 4. Raw authorization parameters (public, both networks)

The model features are secret. The **ISO 8583 / authorization request** fields are not. Any in-flight scorer starts from some subset of:

### Transaction

| Parameter | Typical field | FraudForge today |
|---|---|---|
| Amount | DE 4 | `amount` |
| Currency | DE 49 | (INR assumed) |
| Date/time, hour | DE 7 / 12 / 13 | `hour_of_day` |
| MCC / merchant category | DE 18 | `merchant_category` (from ProductCD) |
| Merchant ID / name / city / country | DE 42 / 43 | `merchant_id`, `country` |
| POS entry mode (chip, contactless, keyed, ecom) | DE 22 | missing |
| POS condition (CNP, recurring, moto) | DE 25 | missing |
| Acquiring institution | DE 32 | missing |
| STAN / RRN / trace | DE 11 / 37 | `transaction_id` |
| Recurring / installments | DE 61 / private | missing |

### Card / account

| Parameter | Typical field | FraudForge today |
|---|---|---|
| PAN token / account | DE 2 | `customer_id` (hash of card1) |
| Expiry | DE 14 | missing |
| Card sequence | DE 23 | missing |
| Service code / product | DE 40 / private | `payment_method` |
| CVV/CVC result (after issuer) | DE 39 / private | missing |
| 3DS / SCA result | 3DS ARes | missing |
| Account age / open date | issuer + network profile | `account_age_days` |

### Channel / auth

| Parameter | Typical field | FraudForge today |
|---|---|---|
| AVS result | DE 44 | missing |
| CSC/CVV result | DE 44 | missing |
| PIN present / verified | DE 52 / 53 | missing |
| Failed auth count | issuer | `failed_auth_count` (ATO only) |
| Wallet / token type (Apple/Google token, COF) | token cryptogram | missing |

### Device / session (ecom; often 3DS / Identity, not classic chip DE)

| Parameter | Source | FraudForge today |
|---|---|---|
| Device ID / fingerprint | 3DS / SDK | `device_id` |
| Device age / first seen | derived | `device_age_days` |
| IP | 3DS / merchant | `ip_id` |
| IP geo, proxy, distance to home | enrichment | `distance_from_home` (IEEE dist1, not true IP) |
| User-agent, OS, screen, timezone, language | Identity Insights inputs | missing |
| Billing vs IP vs shipping distance | Identity Insights | missing |

### Behavioral (derived — this is most of the “500 attributes”)

These are **not** in the ISO message. The network **computes** them from history:

| Family | Examples | FraudForge today |
|---|---|---|
| Velocity | count/amount 1h, 6h, 24h, 7d, 30d | 1h + 24h counts only |
| Amount vs self | z-score vs 30d mean | `avg_amount_30d`, `amount_deviation` |
| Merchant habit | seen this MID before? MCC novelty? | `merchant_risk` (global fraud rate, not personal habit) |
| Geo sequence | last city, km from last txn, country change, travel corridor | single `distance_from_home` |
| Device habit | known device? new device + home IP? | `device_age_days` only |
| Payee / beneficiary | new beneficiary, concentration | `beneficiary_is_new`, `destination_concentration` |
| Network / graph | shared device, mule MID, ring | missing (P2) |
| Time habit | usual hours vs 3am | `hour_of_day` raw, not vs profile |
| Cross-account | same device on many cards | missing |
| Merchant graph | “people like you shop here” (DI inverse recommender) | missing |

**That last table is the real “500 parameters.”** Most are rolling aggregations and relationship features, not extra ISO fields.

---

## 5. How the two products differ (for the lab)

| | VAA-style | DI / DI Pro-style |
|---|---|---|
| Mental model | Many attributes → one fraud likelihood | “Would we expect this merchant/device **for this person**?” |
| History | 2-year profile + global fraud patterns | Sequence + **entity graph** (cardholder–merchant–device) |
| Gen AI | Not the VAA pitch | **Pro:** gen AI + graphs on relationships; still a **score**, not a chatbot on the hot path |
| False declines | Explicitly: still approve infrequent shoppers | Explicitly: new merchant can still be legitimate if relationships fit |
| Latency story | ~1 ms model | Pro &lt; 50 ms; payment path ~hundreds of ms |
| Bank tooling | VRM rules on score + 70+ fields | Score + reason codes + rules cartridges |

For FraudForge: **hot path = VAA-style booster**. **Context overlay = DI-style history_fit / travel / device_match**. Optional narrative is **warm path only**.

---

## 6. What we can honestly implement (parameter shortlist)

Do not invent 500 columns. Implement **families** with 80–200 features after P2.

**Must have to tell the VAA story**

- Amount, hour, MCC, channel (POS vs CNP)
- Device age / known device
- Distance from home **and** distance from last transaction
- Velocity 1h / 24h / 7d
- Merchant seen-before (this customer), merchant risk (portfolio)
- New beneficiary

**Must have to tell the DI story**

- `history_fit`: similarity of this txn to the customer’s 30d centroid (amount, hour, MCC, city)
- `likely_travel`: geo jump + travel-like MCC / prior trips (protective, not a block)
- `device_match` vs `new_device`
- Merchant relationship: “new MID but same MCC cluster as habitual merchants”
- Reason codes: `NEW_DEVICE`, `TRAVEL_PATTERN`, `NEW_PAYEE`, `VELOCITY`

**Do not fake**

- 1 ms as a hardcoded KPI
- 500 attributes we do not compute
- A generative model on the authorization number
- Issuer brand names in the UI

---

## 7. Sources

- [Visa Protect — VAA + VRM](https://www.visa.com/en-us/solutions/secure-card-payments) (400 attributes; VRM 70+ parameters; VDA RNN for CNP)
- [Visa, 17 Jun 2019 — VAA AI press](https://usa.visa.com/about-visa/newsroom/press-releases.releaseId.16421.html) (1 ms; 500+ attributes; score to issuer)
- [Visa EU VAA case study PDF](https://corporate.visa.com/content/dam/VCOM/corporate/solutions/documents/visa-eu-advanced-authorization-case-study.pdf) (2 years history; 500+ attributes)
- [Visa UK Risk Essentials](https://www.visa.co.uk/partner-with-us/issuers-community-europe/solutions/visa-protect/risk-essentials.html)
- PaymentsJournal summary of Visa’s VAA walkthrough (channel, merchant-seen, time, amount, 1–99 score)
- [Decision Intelligence product](https://www.mastercard.com/us/en/business/cybersecurity-fraud-prevention/risk-decisioning/decision-intelligence.html)
- [1 Feb 2024 — DI Pro gen AI press](https://www.mastercard.com/ca/en/news-and-trends/press/2024/february/mastercard-supercharges-consumer-protection-with-gen-ai.html) (account, purchase, merchant, device; &lt;50 ms; relationships)
- Partner overview: score + reason codes in the authorization message
- [Identity Insights data dictionary](https://static.developer.mastercard.com/content/identity-insights-for-accounts/IIA+Synergy+Data+Dictionary.pdf) (device/IP/email parameters — related product)

---

## 8. Pointer

Implementation order after P: `docs/AUTHORIZATION_INTELLIGENCE.md`.
