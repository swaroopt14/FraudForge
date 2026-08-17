# Build a Fraud Typology Library

You should create a **simulation-ready fraud taxonomy**, not just a list of fraud names.

Each fraud type should answer:

```
Who attacks?
Why?
Which channel?
What steps happen?
What payment behavior appears?
What network structure appears?
What AI or agent behavior is involved?
What can the defender observe?
How can it be safely simulated?
What should the blue team do?
```

The taxonomy should distinguish:

- **Unauthorized fraud:** the attacker initiates a payment without the payer’s authorization.
- **Authorized fraud/scam:** the victim is manipulated into authorizing the payment.
- **Identity fraud:** the attacker abuses or fabricates identity.
- **Merchant fraud:** the merchant or merchant infrastructure is fraudulent.
- **Network fraud:** multiple entities coordinate.
- **Agentic fraud:** an AI agent or tool performs or alters payment actions.

This distinction is consistent with European payment-fraud taxonomies, which separate unauthorized transactions from authorized payments initiated after the payer is manipulated.[[ecb.europa](https://www.ecb.europa.eu/press/intro/publications/pdf/ecb.ebaecb202512.es.pdf)][[europeanpaymentscouncil](https://www.europeanpaymentscouncil.eu/sites/default/files/kb/file/2025-12/EPC162-24%20v2.0%202025%20Payments%20Threats%20and%20Fraud%20Trends%20Report_0.pdf)][[abe-eba](https://www.abe-eba.eu/wp-content/uploads/2025/06/jpss_18_1_jpss0006_a-pan_european-fraud-taxonomy.pdf)]

---

# 1. Recommended Library Structure

```
fraud_library/
├── taxonomy/
│   ├── fraud_families.yaml
│   ├── attack_surfaces.yaml
│   ├── payment_rails.yaml
│   └── lifecycle_stages.yaml
├── fraud_types/
│   ├── unauthorized/
│   ├── authorized_scams/
│   ├── identity/
│   ├── card/
│   ├── account/
│   ├── merchant/
│   ├── network/
│   ├── digital_channels/
│   └── agentic/
├── scenarios/
│   ├── replay/
│   ├── mutation/
│   └── composite/
├── simulator_templates/
├── detection_signals/
├── mitigation_playbooks/
├── sources/
├── attack_history/
└── blue_team_reports/
```

Each fraud type should have:

```
fraud_type.yaml
simulation_template.py
detection_features.yaml
mitigation_playbook.yaml
historical_sources.json
```

---

# 2. Universal Fraud Record

Use one schema for every fraud type.

```
from pydantic import BaseModel
from typing import Literal

class FraudType(BaseModel):
    fraud_id: str
    name: str
    version: str = "1.0"

    family: str
    subfamily: str
    category: Literal[
        "unauthorized",
        "authorized_scam",
        "identity",
        "card",
        "account",
        "merchant",
        "network",
        "agentic"
    ]

    payment_rails: list[str]
    geographies: list[str]
    lifecycle_stages: list[str]

    attacker_types: list[str]
    victim_types: list[str]
    objective: list[str]

    preconditions: list[str]
    attack_steps: list[dict]

    genai_role: list[str]
    agent_role: list[str]
    network_role: list[str]

    payment_behavior: dict
    network_behavior: dict
    identity_behavior: dict
    agent_behavior: dict
    intent_behavior: dict

    observable_signals: list[str]
    evasion_methods: list[str]

    simulator_template: str
    simulation_parameters: dict
    realism_constraints: list[str]

    prevention_controls: list[str]
    detection_controls: list[str]
    verification_controls: list[str]
    containment_controls: list[str]
    recovery_controls: list[str]

    historical_status: str
    sources: list[str]
    simulatable: bool
    safety_status: str
```

---

# 3. Complete Fraud Taxonomy

## Family A: Card and payment-instrument fraud

### A1. Card-not-present fraud

**How it happens:** Stolen card details are used online or in apps without the physical card.

**Payment behavior:**

- New merchant.
- Unusual amount.
- Unusual country or device.
- Multiple attempts.
- Different shipping and billing context.
- Rapid use after credential compromise.

**Signals:**

- Device and IP risk.
- Card testing pattern.
- Merchant velocity.
- Amount deviation.
- Authentication result.
- Customer location mismatch.

**Simulation:** Start with legitimate e-commerce transactions and alter device, merchant, amount, timing, and authentication context.

**Mitigation:** Approve, step-up, or block based on risk; do not generate real card numbers.

---

### A2. Card testing

**How it happens:** Attackers test whether stolen card details work using many small authorizations.

**Payment behavior:**

- Small amounts.
- Repeated attempts.
- Many cards against one merchant.
- Same device/IP or automation fingerprint.
- High decline rate.

**Network structure:**

```
Many cards → one merchant
Many cards → one device/IP
```

**Simulation:** Generate low-value bursts across synthetic cards, merchants, devices, and IPs.

**Signals:**

- Authorization velocity.
- Decline-to-approval ratio.
- Card-to-device count.
- Merchant concentration.
- Repeated amount patterns.

**Mitigation:** Rate limiting, step-up, merchant review, temporary hold.

---

### A3. Lost or stolen physical card

**How it happens:** A physical payment instrument is used after theft.

**Signals:**

- Location discontinuity.
- New merchant category.
- Contactless velocity.
- Device or terminal context.
- Sudden behavior change.

**Simulation:** Create a customer baseline, then generate transactions with abnormal geography and merchant categories.

---

### A4. Skimming and payment-data compromise

**How it happens:** Payment data is captured through compromised terminals, websites, or digital-skimming infrastructure.

**Network behavior:**

- Many cards later used at related merchants or infrastructure.
- Common compromise window.
- Shared merchant or domain indicators.

**Simulation:** Generate a compromise event followed by coordinated downstream card use.

**Important:** Simulate the compromise metadata; do not implement skimming or credential theft.

---

### A5. Contactless or terminal abuse

**How it happens:** Repeated or unusual transactions exploit weak controls around terminals or unattended payments.

**Signals:**

- Repeated small payments.
- Terminal concentration.
- Abnormal time pattern.
- Customer location mismatch.
- Excessive contactless usage.

---

## Family B: Account and identity fraud

### B1. Account takeover

**How it happens:** An attacker gains control of an existing account and changes payment behavior.

**Attack sequence:**

```
Credential compromise
→ Login
→ Device or contact change
→ Beneficiary addition
→ Payment
→ Cash-out
```

**Signals:**

- New device.
- New IP or location.
- Password reset.
- SIM/contact change.
- New beneficiary.
- Login-to-payment timing.
- Transaction behavior deviation.

**Simulation:** Generate a normal account history, then inject a takeover sequence with controlled changes.

**Mitigation:** Step-up authentication, beneficiary cooling-off period, account hold, session revocation.

---

### B2. Credential stuffing

**How it happens:** Previously exposed username/password combinations are tried across accounts.

**Signals:**

- High login failure rate.
- Many accounts from common infrastructure.
- Similar timing.
- Successful login followed by payment.
- Device or IP reuse.

**Simulation:** Generate synthetic login events and link successful sessions to later payment events.

---

### B3. Phishing-based account compromise

**How it happens:** A fake message or site persuades the victim to disclose credentials or approve an action.

**AI role:**

- Personalized messages.
- Multilingual variation.
- Conversation automation.
- Brand impersonation.

**Simulation:** Do not send messages. Create synthetic communication events with:

```
channel
sender risk
link risk
urgency
victim interaction
login event
payment event
```

RBI specifically warns about fraudulent messages, fake calls, unknown links, unauthorized QR codes, phishing, vishing, and misuse of UPI collect requests.[[rbi.org](http://rbi.org)]

---

### B4. SIM-swap-assisted fraud

**How it happens:** Control of the phone number is transferred or abused, weakening OTP-based controls.

**Signals:**

- SIM-change event.
- New device.
- Number portability or carrier change.
- Password reset.
- New beneficiary.
- Payment shortly after identity changes.

**Simulation:** Represent SIM change as a synthetic event before account takeover and payment.

---

### B5. Synthetic identity fraud

**How it happens:** Real and fabricated identity elements are combined to create a new persona.

**Network structure:**

```
Many synthetic identities
→ shared device/address/contact infrastructure
→ common merchants or beneficiaries
```

FATF has described synthetic identities as combinations of real and fake information used to create identities that can be used to open accounts.[[fatf-gafi](https://www.fatf-gafi.org/content/dam/fatf-gafi/guidance/Guidance-on-Digital-Identity.pdf)]

**Signals:**

- Identity inconsistency.
- Shared device and contact information.
- Multiple accounts created near the same time.
- Behavior similarity.
- Credit or payment activity inconsistent with identity age.

---

### B6. Identity impersonation

**How it happens:** An attacker pretends to be a customer, bank employee, merchant, government official, or support agent.

**Simulation:** Generate a synthetic actor-role event and subsequent authorized or unauthorized payment.

---

### B7. KYC and onboarding fraud

**How it happens:** False, altered, or synthetic identity information is used during account opening.

**Signals:**

- Document inconsistency.
- Liveness or identity mismatch.
- Device reuse.
- Multiple applications from shared infrastructure.
- Identity data reused across profiles.

**Simulation:** Use risk metadata, not real document forgery.

---

### B8. Deepfake identity fraud

**How it happens:** Generated or manipulated face, voice, or video is used to impersonate a customer or official.

**Simulation:**

```
voice_verification_risk = 0.78
liveness_confidence = 0.42
identity_document_consistency = 0.51
```

Do not generate actual fake identity media for the demo.

---

## Family C: Authorized payment scams

### C1. Purchase scam

**How it happens:** A victim pays for goods or services that do not exist or are never delivered.

**Signals:**

- New merchant.
- Price or urgency anomaly.
- Merchant age and reputation.
- Repeated complaints.
- Payment destination risk.

**Simulation:** Generate a legitimate-looking purchase followed by a simulated non-delivery outcome.

---

### C2. Investment scam

**How it happens:** A victim is persuaded to send payments to a fraudulent investment scheme.

**Signals:**

- New beneficiary.
- High urgency.
- Repeated escalating payments.
- Multiple victims paying one beneficiary.
- Merchant or beneficiary cluster.
- Cross-channel communication events.

**Simulation:** Create multiple victim accounts sending staged payments to a common beneficiary.

---

### C3. Romance or relationship scam

**How it happens:** A long-term social relationship is used to persuade the victim to transfer money.

**Signals:**

- Repeated payments over time.
- New beneficiary.
- Unusual geography.
- Increasing payment amounts.
- Communication-to-payment timing.
- Multiple victims connected to one destination.

**Simulation:** Use synthetic communication metadata, not real conversations.

---

### C4. Advance-fee scam

**How it happens:** The victim is promised a benefit but must pay an upfront fee.

**Signals:**

- Urgent payment.
- Repeated small payments.
- New beneficiary.
- Common scam language or communication pattern.
- Multiple victims to one destination.

---

### C5. Impersonation scam

**How it happens:** Fraudster impersonates a bank, police officer, government department, employer, family member, or service provider.

**Simulation:** Represent:

```
impersonated_role
communication_channel
urgency
payment_request
beneficiary
victim_action
```

---

### C6. Invoice redirection or business email compromise

**How it happens:** Payment instructions are altered so a legitimate business payment goes to a fraudulent account.

**Signals:**

- Beneficiary change.
- Invoice metadata mismatch.
- New bank account.
- Similar sender/domain.
- Unusual approval chain.
- Payment amount may remain entirely normal.

**Simulation:** Keep amount and merchant normal while changing beneficiary and approval provenance.

---

### C7. Fake refund scam

**How it happens:** A fraudster claims a refund is due and tricks the victim into making a payment or revealing information.

**Signals:**

- Refund request inconsistent with transaction history.
- New beneficiary.
- Support impersonation.
- Urgency.
- Collect request or payment-link behavior.

---

### C8. Courier or parcel scam

**How it happens:** A victim is told that a parcel, customs fee, or legal issue requires payment.

**Signals:**

- New payment destination.
- Small urgent payment.
- Link or QR interaction.
- Communication/payment timing.
- Many victims using one beneficiary.

---

### C9. Loan or employment scam

**How it happens:** The victim is promised a loan or job but must pay a processing, verification, or training fee.

**Signals:**

- Repeated advance payments.
- New beneficiary.
- Similar narrative across victims.
- Account or merchant cluster.
- Escalation after each payment.

---

## Family D: India-specific digital-payment fraud

### D1. UPI collect-request fraud

**How it happens:** The fraudster sends a collect request under the pretext of receiving a refund, reward, sale payment, or transfer.

RBI specifically warns that victims may be tricked into approving fake UPI collect requests and entering their UPI PIN; a UPI PIN authorizes payment rather than receiving money.[[rbi.org](http://rbi.org)]

**Simulation:**

```
communication_event
→ collect_request_created
→ victim_prompted
→ authorization_attempt
→ payment_to_new_beneficiary
```

**Signals:**

- First-time beneficiary.
- Collect request instead of expected receive flow.
- Urgent message.
- Beneficiary risk.
- Customer behavior deviation.

---

### D2. QR-code payment redirection

**How it happens:** A QR code is replaced or presented as a way to receive money, but scanning it initiates payment to the attacker.

RBI warns about unauthorized QR codes and QR-based fraud.[[rbi.org](http://rbi.org)]

**Simulation:**

```
expected_merchant = merchant_a
actual_qr_destination = beneficiary_b
destination_changed = true
```

**Signals:**

- QR destination mismatch.
- New beneficiary.
- Merchant identity inconsistency.
- Device or location anomaly.
- Payment intent mismatch.

---

### D3. Fake customer-support fraud

**How it happens:** An attacker impersonates a bank, wallet, or payment-app support representative.

**Simulation:** Create:

```
support_contact_event
identity_claim
verification_request
beneficiary_change
payment_event
```

---

### D4. Fake payment app or website

**How it happens:** A lookalike app or site captures information or manipulates payment instructions.

**Simulation:** Use:

```
app_trust_score
domain_age
merchant_identity_match
tool_provenance
```

Do not simulate credential collection.

---

### D5. Cashback and reward scam

**How it happens:** The victim is promised cashback, prizes, or rewards and is asked to authorize a payment or disclose information.

---

### D6. WhatsApp and social-commerce fraud

**How it happens:** Fraudsters use messaging platforms, fake sellers, fake support, or investment groups to direct payments.

**Signals:**

- Communication-to-payment correlation.
- New beneficiary.
- Repeated social channel.
- Multiple victims.
- Merchant identity mismatch.

---

### D7. Digital lending fraud

**How it happens:** Fake or abusive loan services collect fees, misuse identity data, or pressure victims into payments.

**Signals:**

- Advance-fee pattern.
- Multiple small payments.
- High-pressure communications.
- Identity and device reuse.
- Common beneficiary cluster.

---

### D8. Aadhaar or identity-document misuse

**How it happens:** Identity information is misused during onboarding or account access.

**Simulation:** Use abstract identity-risk events only:

```
document_reuse_score
identity_consistency_score
liveness_score
```

Never store real Aadhaar data in your prototype.

---

## Family E: Merchant and e-commerce fraud

### E1. Fraudulent merchant

**How it happens:** A merchant account is created or used to receive fraudulent payments.

**Signals:**

- Website and business mismatch.
- High chargebacks.
- Customer concentration.
- Shared infrastructure with other merchants.
- Unusual settlement behavior.

---

### E2. Merchant collusion

**How it happens:** Multiple merchants coordinate to fabricate transactions, move funds, or evade controls.

**Network structure:**

```
Merchant A
Merchant B
Merchant C
    ↓
Common owner/device/IP/beneficiary
```

---

### E3. Transaction laundering

**How it happens:** A legitimate merchant processes payments for another undisclosed or prohibited business.

**Signals:**

- Product/category mismatch.
- Descriptor mismatch.
- Customer and transaction patterns inconsistent with stated business.
- Shared settlement accounts.
- Merchant network similarity.

---

### E4. Friendly fraud

**How it happens:** A legitimate customer disputes an authorized purchase falsely or claims non-receipt.

**Signals:**

- Repeated disputes.
- Customer-merchant relationship.
- Delivery or usage evidence.
- Dispute timing.
- Device and account history.

---

### E5. Refund abuse

**How it happens:** Fraudsters exploit refund workflows using false claims, duplicate requests, or manipulated returns.

**Simulation:** Generate purchase → refund request → repeated refund or refund-to-new-destination sequence.

---

### E6. Return abuse

**How it happens:** Goods are returned fraudulently, substituted, or claimed as undelivered.

**Signals:**

- High return rate.
- Account and device relationships.
- Repeated merchant behavior.
- Refund destination changes.

---

## Family F: Transfer, wallet, and bank fraud

### F1. Unauthorized bank transfer

**How it happens:** An attacker gains access and initiates a payment without the customer’s authorization.

**Signals:**

- Session, device, IP, authentication, and beneficiary changes.
- Login-to-payment timing.
- Behavioral deviation.

---

### F2. Authorized push-payment fraud

**How it happens:** The payer is manipulated into authorizing a transfer to a fraudster-controlled account.

European payment-fraud reporting identifies manipulation of the payer into initiating a credit transfer as a major authorized-fraud category.[[ecb.europa](https://www.ecb.europa.eu/press/intro/publications/pdf/ecb.ebaecb202512.es.pdf)]

**Signals:**

- New payee.
- Urgency.
- Payment behavior change.
- Multiple victims to one destination.
- Cross-channel evidence.
- Beneficiary risk.

---

### F3. Wallet takeover

**How it happens:** An attacker gains control of a digital wallet and transfers or spends funds.

**Signals:**

- New device.
- Key or credential change.
- Unusual address or beneficiary.
- Rapid transfer sequence.
- New geography.

---

### F4. Wallet drain

**How it happens:** A compromised wallet is emptied through many transfers or approvals.

**Simulation:** Generate an initial compromise event followed by rapid multi-destination or single-destination transfers.

---

### F5. Unauthorized direct debit or ACH fraud

**How it happens:** An unauthorized debit is created or an existing mandate is abused.

**Signals:**

- New mandate.
- Unexpected merchant.
- Amount deviation.
- Repeated debit pattern.
- Account history mismatch.

---

### F6. Payment mandate abuse

**How it happens:** A legitimate recurring authorization is manipulated or reused beyond its intended scope.

**Signals:**

- Amount or frequency change.
- Merchant identity change.
- Mandate age mismatch.
- Destination change.
- Intent scope violation.

---

## Family G: Money movement and financial crime networks

### G1. Mule-account network

**How it happens:** Multiple accounts receive, split, transfer, and cash out illicit funds.

**Signals:**

- Many senders to one beneficiary.
- Shared devices or IPs.
- Rapid outflow.
- New account activity.
- Coordinated timing.

---

### G2. Layering network

**How it happens:** Funds move through several accounts to obscure origin.

**Graph structure:**

```
Source → Account A → Account B → Account C → Beneficiary
```

**Signals:**

- Short holding times.
- Multiple hops.
- Repeated amounts.
- Circular or fan-out/fan-in flow.
- Suspicious community membership.

---

### G3. Fan-in network

```
Many accounts → one recipient
```

Often relevant to collection, mule, and scam networks.

---

### G4. Fan-out network

```
One source → many accounts
```

Can indicate distribution, layering, payroll-like legitimate behavior, or coordinated fraud.

---

### G5. Circular flow

```
A → B → C → A
```

**Signals:**

- Repeated cycles.
- Short time intervals.
- Similar amounts.
- Shared infrastructure.

---

### G6. Beneficiary concentration

**How it happens:** Multiple apparently unrelated customers send money to one recipient or small recipient cluster.

**Signals:**

- Sender count.
- Concentration ratio.
- New-edge velocity.
- Account and device relationships.

---

## Family H: AI-generated social and identity fraud

### H1. AI phishing

**How it happens:** AI generates personalized messages, fake links, and plausible business language.

**Simulation:** Generate message-risk metadata, not real phishing campaigns.

---

### H2. Voice-cloning scam

**How it happens:** A synthetic voice impersonates a trusted person or institution.

**Simulation:** Use:

```
voice_similarity_score
caller_identity_confidence
call_context_risk
payment_urgency
```

---

### H3. Deepfake video impersonation

**How it happens:** A fake video or live interaction impersonates a trusted person.

**Simulation:** Use synthetic verification scores and event metadata only.

---

### H4. AI-generated multilingual scam

**How it happens:** Attackers create localized messages in different languages and dialects.

**Signals:**

- Communication pattern.
- Link and sender risk.
- Cross-channel correlation.
- Payment behavior.

---

### H5. AI-generated fake merchant

**How it happens:** GenAI produces convincing product pages, support conversations, reviews, and merchant descriptions.

**Signals:**

- Merchant infrastructure.
- Domain age.
- Product/category inconsistency.
- Payment destination risk.
- Common infrastructure with other merchants.

---

## Family I: Agentic AI fraud

### I1. Malicious AI agent

**How it happens:** An agent is intentionally designed to conduct unauthorized or fraudulent payments.

**Signals:**

- Agent identity.
- Tool usage.
- Transaction scope.
- Destination.
- Behavior baseline.
- Intent compliance.

---

### I2. Compromised legitimate agent

**How it happens:** An approved agent is taken over or its policy/context is altered.

**Signals:**

- Behavioral drift.
- New tools.
- New merchants.
- New transaction hours.
- Increased payment frequency.
- Intent violations.

---

### I3. Agent impersonation

**How it happens:** An attacker pretends to be a trusted agent.

**Signals:**

- Signature or attestation failure.
- Credential reuse.
- Directory mismatch.
- Behavioral mismatch.
- Tool or network inconsistency.

---

### I4. Unauthorized delegation

**How it happens:** An agent acts for a user or account without valid permission.

**Signals:**

- Missing intent.
- Expired intent.
- Invalid authority chain.
- Unknown agent-owner relationship.

---

### I5. Excessive agent permission

**How it happens:** The agent has more spending authority than required.

**Signals:**

- Capability-to-task mismatch.
- High spend limit.
- Broad merchant category permissions.
- No expiry.
- No human approval requirement.

---

### I6. Intent manipulation

**How it happens:** The executed transaction differs from what the user authorized.

**Signals:**

- Amount mismatch.
- Category mismatch.
- Merchant mismatch.
- Beneficiary mismatch.
- Currency or geography mismatch.
- Cumulative-spend violation.

---

### I7. Tool hijacking

**How it happens:** A tool or external service returns manipulated data or instructions.

**Signals:**

- Tool provenance.
- Tool version.
- Output schema changes.
- Destination changes after tool call.
- Tool used by suspicious agents.

---

### I8. Prompt injection

**How it happens:** Instructions in user input or external content change agent behavior.

**Simulation:** Represent an untrusted content event and a resulting policy deviation. Do not create live exploit payloads.

---

### I9. Indirect prompt injection

**How it happens:** Malicious instructions are embedded in merchant pages, product descriptions, documents, or API responses.

**Signals:**

- Untrusted content source.
- Tool output contains instruction-like fields.
- Agent plan changes after external content.
- Payment parameter delta.

---

### I10. Spending-limit abuse

**How it happens:** The agent performs many individually acceptable transactions that exceed the intended cumulative limit.

**Signals:**

- Cumulative intent spend.
- Transaction fragmentation.
- Number of merchants.
- Time-window velocity.
- Repeated beneficiary.

---

### I11. Agent-to-agent fraud

**How it happens:** Agents coordinate to manipulate another agent or payment process.

**Network structure:**

```
Agent A → Agent B → Merchant tool → Payment agent → Beneficiary
```

**Signals:**

- Shared tools.
- Shared wallets.
- Similar timing.
- Similar prompts or plans.
- Common destinations.
- Unexpected inter-agent communication.

---

### I12. Agent credential theft

**How it happens:** Agent identity or authorization credentials are misused.

**Signals:**

- Key use from new location.
- Replay.
- Unusual transaction volume.
- Invalid attestation.
- New tool or merchant relationships.

---

# 4. Fraud Library Record Example

## UPI collect-request fraud

```
fraud_id: FRAUD-UPI-001
name: UPI collect-request scam
version: "1.0"

family: authorized_scam
subfamily: collect_request
category: authorized_scam

payment_rails:
  - UPI

geographies:
  - IN

lifecycle_stages:
  - social_engineering
  - payment_preparation
  - authorization
  - settlement

attacker_types:
  - human_fraudster
  - fraud_organization
  - malicious_merchant

victim_types:
  - retail_customer
  - marketplace_user

objective:
  - trick_victim_into_authorizing_payment
  - redirect_payment_to_attacker

preconditions:
  - victim_has_UPI_access
  - attacker_can_contact_victim
  - collect_requests_are_enabled

attack_steps:
  - step: create_pretext
    action: impersonate_refund_or_buyer
  - step: send_collect_request
    action: request_payment_from_victim
  - step: create_urgency
    action: pressure_victim_to_approve
  - step: receive_payment
    action: settle_to_attacker_beneficiary

genai_role:
  - personalized_social_engineering
  - multilingual_message_generation

agent_role: []

network_role:
  - repeated_victims_to_common_beneficiary

payment_behavior:
  amount_strategy: small_or_medium
  beneficiary_strategy: new_beneficiary
  velocity_strategy: repeated_requests
  authorization_type: victim_authorized

network_behavior:
  beneficiary_sender_count: high
  victim_beneficiary_edges: rapidly_created

identity_behavior:
  impersonated_role: bank_or_buyer

agent_behavior: {}
intent_behavior: {}

observable_signals:
  - new_beneficiary
  - collect_request_instead_of_expected_receive
  - urgent_communication
  - beneficiary_risk
  - multiple_victims_to_same_beneficiary

evasion_methods:
  - use_normal_amount
  - vary_message_text
  - use_multiple_beneficiaries

simulator_template: upi_collect_request_v1

simulation_parameters:
  victim_count: 50
  beneficiary_count: 3
  request_interval_minutes: 20

realism_constraints:
  - amount_must_be_positive
  - beneficiary_must_exist_before_payment
  - collect_request_precedes_payment
  - no_real_UPI_calls

prevention_controls:
  - user_warning
  - beneficiary_reputation
  - collect_request_context

detection_controls:
  - graph_risk
  - beneficiary_velocity
  - behavior_deviation

verification_controls:
  - explicit_payment_confirmation
  - trusted_channel_callback

containment_controls:
  - hold_payment
  - beneficiary_review

recovery_controls:
  - dispute_flow
  - beneficiary_freeze
  - victim_notification

historical_status: historical_pattern
sources:
  - RBI-2022-UPI-WARNING

simulatable: true
safety_status: approved
```

RBI’s public warning specifically discusses phishing, vishing, fake links, unauthorized QR codes, and fraudulent UPI collect requests, making it an appropriate primary source for this library entry.[[rbi.org](http://rbi.org)]

---

# 5. Simulation Template Design

Every fraud type should map to a deterministic simulator.

```
class FraudSimulator:
    template_id: str

    def validate(self, params):
        ...

    def create_entities(self, params, rng):
        ...

    def create_events(self, params, entities, rng):
        ...

    def create_transactions(self, params, entities, rng):
        ...

    def create_network_edges(self, params, entities, rng):
        ...

    def create_ground_truth(self, params):
        ...

    def expected_signals(self, params):
        ...
```

## Example templates

```
card_testing_v1
account_takeover_v1
synthetic_identity_v1
mule_network_v1
upi_collect_request_v1
qr_destination_substitution_v1
invoice_redirection_v1
refund_abuse_v1
agent_intent_scope_v1
agent_tool_hijacking_v1
spending_fragmentation_v1
beneficiary_concentration_v1
```

---

# 6. Fraud Simulation Fields

Each simulated event should include:

```
fraud_id
attack_instance_id
stage
timestamp
customer_id
account_id
merchant_id
beneficiary_id
device_id
ip_id
agent_id
intent_id
payment_rail
amount
currency
authentication_method
transaction_status
is_fraud
attack_family
network_cluster_id
risk_signals
```

Add provenance:

```
{
    "source_type": "synthetic",
    "source_template": "mule_network_v1",
    "seed": 42,
    "generator_version": "0.3.0",
    "ground_truth_reason": "beneficiary_concentration"
}
```

---

# 7. Fraud Simulation Modes

## Replay

Recreate one known pattern.

```
Historical pattern
→ fixed scenario
→ synthetic replay
```

## Mutate

Change:

- Amount.
- Timing.
- Merchant.
- Device.
- IP.
- Beneficiary.
- Agent.
- Intent.
- Network size.

```
Known attack
→ controlled mutation
→ new variant
```

## Compose

Combine multiple fraud patterns:

```
account takeover
+
mule network
+
spending fragmentation
```

## Escalate

Increase complexity:

```
single transaction
→ sequence
→ network
→ agent
→ coordinated agent network
```

Your library should store the generation mode because a composite hypothesis is not a historical fact.

---

# 8. Defining “Every Type”

You should not aim for an impossible list of every fraud variant. Instead, build a taxonomy that covers the major **mechanisms**.

A useful completeness test is coverage across these dimensions:

```
Who is attacked?
What is stolen?
Who authorizes?
Which payment rail?
Which channel?
Which identity layer?
Which network structure?
Which agent behavior?
Which settlement outcome?
```

## Coverage matrix


| Dimension     | Examples                                                               |
| ------------- | ---------------------------------------------------------------------- |
| Victim        | Consumer, merchant, bank, agent, platform                              |
| Asset         | Credential, card, account, identity, payment authorization             |
| Authorization | Unauthorized, socially authorized, delegated agent authorization       |
| Channel       | Card, UPI, wallet, bank transfer, QR, API, merchant checkout           |
| Attack stage  | Onboarding, login, payment, settlement, refund, recovery               |
| Actor         | Human, organization, bot, malicious merchant, compromised agent        |
| Structure     | Single row, sequence, ring, fan-in, fan-out, multi-agent graph         |
| AI role       | Content generation, identity generation, planning, adaptation, evasion |
| Outcome       | Theft, redirection, laundering, refund loss, account compromise        |


If your library covers these dimensions, it will have broad coverage without needing thousands of duplicated fraud names.

---

# 9. Blue-Team Mapping for Every Fraud Type

Every record should have this structure:

```
ATTACK
  ↓
SIGNALS
  ↓
MODEL
  ↓
POLICY
  ↓
ACTION
```

## Example: account takeover

```
Attack:
new device + credential compromise + beneficiary addition

Signals:
new_device
login_to_payment_time
new_beneficiary
location_deviation
device_account_degree

Models:
transaction classifier
behavior model
graph risk

Policy:
if new device + new beneficiary + high risk:
    step-up or hold

Action:
STEP_UP
or BLOCK
```

## Example: agent destination substitution

```
Attack:
merchant tool changes destination

Signals:
destination_changed
intent_destination_mismatch
tool_provenance_gap
beneficiary_risk

Models:
transaction risk
agent behavior model
beneficiary graph model

Policy:
destination mismatch requires reauthorization

Action:
BLOCK
revoke tool
create investigation case
```

---

# 10. Building the Library in Phases

## Phase 1: Core payment fraud

Start with:

```
card-not-present
card testing
account takeover
low-and-slow fraud
```

## Phase 2: Network fraud

Add:

```
mule network
shared device
shared IP
beneficiary concentration
merchant collusion
```

## Phase 3: India-specific fraud

Add:

```
UPI collect request
QR substitution
fake support
fake refund
WhatsApp payment scam
SIM-swap sequence
```

## Phase 4: Agentic fraud

Add:

```
intent scope abuse
destination substitution
spending fragmentation
malicious tool
compromised agent
agent impersonation
agent behavioral drift
```

## Phase 5: Composite attacks

Combine:

```
account takeover + mule network
synthetic identity + shared device
agent tool hijacking + destination substitution
UPI scam + beneficiary concentration
compromised agent + spending fragmentation
```

## Phase 6: Adaptive red teaming

Use blue-team failures to generate variants that:

- Preserve realistic behavior.
- Avoid the strongest detector features.
- Retain the attack objective.
- Change network and timing structure.
- Remain within simulator constraints.

---

# 11. Recommended Initial Library

Start with these 25 records:


| ID    | Fraud type                     | Category        | Template                       |
| ----- | ------------------------------ | --------------- | ------------------------------ |
| F-001 | Card-not-present               | Unauthorized    | `cnp_v1`                       |
| F-002 | Card testing                   | Unauthorized    | `card_testing_v1`              |
| F-003 | Lost/stolen card               | Unauthorized    | `stolen_card_v1`               |
| F-004 | Account takeover               | Unauthorized    | `account_takeover_v1`          |
| F-005 | Credential stuffing            | Unauthorized    | `credential_stuffing_v1`       |
| F-006 | SIM-swap fraud                 | Unauthorized    | `sim_swap_v1`                  |
| F-007 | Synthetic identity             | Identity        | `synthetic_identity_v1`        |
| F-008 | KYC fraud                      | Identity        | `kyc_risk_v1`                  |
| F-009 | UPI collect scam               | Authorized scam | `upi_collect_request_v1`       |
| F-010 | QR destination swap            | Authorized scam | `qr_substitution_v1`           |
| F-011 | Fake support scam              | Authorized scam | `fake_support_v1`              |
| F-012 | Purchase scam                  | Authorized scam | `purchase_scam_v1`             |
| F-013 | Investment scam                | Authorized scam | `investment_scam_v1`           |
| F-014 | Romance scam                   | Authorized scam | `romance_scam_v1`              |
| F-015 | Invoice redirection            | Authorized scam | `invoice_redirect_v1`          |
| F-016 | Refund abuse                   | Merchant        | `refund_abuse_v1`              |
| F-017 | Friendly fraud                 | Merchant        | `friendly_fraud_v1`            |
| F-018 | Fraudulent merchant            | Merchant        | `merchant_fraud_v1`            |
| F-019 | Mule network                   | Network         | `mule_network_v1`              |
| F-020 | Shared-device network          | Network         | `shared_device_v1`             |
| F-021 | Beneficiary concentration      | Network         | `beneficiary_concentration_v1` |
| F-022 | Layering network               | Network         | `layering_v1`                  |
| F-023 | Agent intent abuse             | Agentic         | `intent_scope_v1`              |
| F-024 | Agent destination substitution | Agentic         | `destination_substitution_v1`  |
| F-025 | Malicious tool                 | Agentic         | `tool_hijacking_v1`            |


Do not implement all 25 immediately. Create the records first, then implement the five highest-value templates.

---

# 12. Best Five Templates for Your Prototype

Build these first:

## 1. Account takeover

Demonstrates:

```
identity
→ device
→ behavior
→ payment
```

## 2. Mule network

Demonstrates:

```
network graph
→ coordinated transactions
→ beneficiary concentration
```

## 3. UPI collect or QR substitution

Demonstrates:

```
India-specific scam
→ authorized payment
→ destination mismatch
```

## 4. Agent intent scope abuse

Demonstrates:

```
AI agent
→ delegated authority
→ intent violation
```

## 5. Composite adaptive attack

Demonstrates:

```
historical patterns
→ GenAI composition
→ realistic mutation
→ red/blue closed loop
```

These five give you strong breadth across unauthorized fraud, authorized fraud, network fraud, India-specific fraud, and agentic fraud.

---

# 13. Frontend Library View

## Fraud taxonomy dashboard

```
FRAUD LIBRARY

Total fraud types       25
Historical patterns     14
Research-derived         6
Synthetic composites     5
Simulatable              18
Agentic                  7
Network-based            9
India-specific           6
```

## Fraud-type card

```
UPI collect-request scam
Authorized scam • UPI • India

How it happens:
Fraudster sends a fake collect request under the pretext
of a refund or payment receipt. The victim authorizes the
request, causing money to leave the account.

Network pattern:
Multiple victims → small beneficiary cluster

AI role:
Personalized multilingual social engineering

Signals:
New beneficiary • collect request • urgency • beneficiary risk

Simulator:
upi_collect_request_v1

[Replay] [Mutate] [Compose]
```

## Generation controls

```
Generation mode:
[Replay historical] [Mutate] [Compose novel]

Base fraud:
[UPI collect-request scam]

Add pattern:
[Mule network]

Add agent behavior:
[None / compromised agent / malicious tool]

Evasion:
[normal amount] [low velocity] [known device]

[Generate simulation]
```

---

# 14. Key Rule for Your Red Team

Do not ask GenAI:

```
Generate a new fraud.
```

Ask it:

```
Using these historical patterns, generate a candidate composite
payment-fraud hypothesis that:
- preserves realistic transaction distributions,
- introduces a new network or agent relationship,
- has a clear attacker objective,
- has measurable observable signals,
- can be compiled using available simulation templates,
- remains simulation-only,
- and is different from previous attack history.
```

This produces structured novelty rather than fictional storytelling.

# Final recommendation

Your fraud library should be a **versioned, evidence-backed, compositional simulation library** with:

```
Fraud types
+ historical incidents
+ attack patterns
+ payment behaviors
+ network motifs
+ agent/intent behaviors
+ simulator templates
+ detection signals
+ mitigation playbooks
+ attack history
+ blue-team feedback
```

The core red-team loop becomes:

```
Historical fraud
        ↓
Structured fraud pattern
        ↓
Replay
        ↓
Mutation
        ↓
Composition with another pattern
        ↓
Novel attack hypothesis
        ↓
Realism and safety validation
        ↓
Synthetic transaction + network + agent events
        ↓
Blue-team evaluation
        ↓
Harder variant
```

That gives you a library capable of generating fraud with **breadth across fraud families** and **depth across identity, behavior, networks, agents, intent, and settlement**, while keeping every generated attack measurable and safe to simulate.