This data model supports:

```
Threat Library
→ Red-Team Controller
→ Known and Novel Attacks
→ Attack Compiler
→ Simulation Engine
→ Transaction / Network / Agent Events
→ Blue-Team Detection
→ Evaluation
→ Closed Loop
```

  
`docs/DATA_MODEL.md`

Copy this into:

```
docs/DATA_MODEL.md
```

This data model supports:

```
Threat Library
→ Red-Team Controller
→ Known and Novel Attacks
→ Attack Compiler
→ Simulation Engine
→ Transaction / Network / Agent Events
→ Blue-Team Detection
→ Evaluation
→ Closed Loop
```

```
# Adversarial Payment Defense Lab

## Data Model Specification

Version: 0.1.0  
Status: Draft  
Owner: FraudForge Engineering

---

## 1. Purpose

This document defines the canonical data model for the Adversarial Payment Defense Lab.

The model supports:

- Synthetic payment generation.
- Historical fraud replay.
- Red-team attack mutation.
- Novel attack composition.
- Network and graph simulation.
- Agent and intent simulation.
- Blue-team risk scoring.
- Explainable decisions.
- Adversarial evaluation.
- Closed-loop red/blue learning.

The model separates:

1. Source and evidence data.
2. Simulation entities.
3. Payment and network events.
4. Attack specifications.
5. Model features.
6. Ground truth.
7. Evaluation results.

---

## 2. Data Provenance Principles

Every field must identify where it came from.

```text
public
derived
synthetic
simulated
model_generated
post_event
```

Every dataset must also identify when a field is available.

```text
before_authorization
at_authorization
after_authorization
post_event_only
simulation_only
```

A model used for authorization-time detection must not receive:

- Future transactions.
- Confirmed fraud labels.
- Chargeback outcomes.
- Blue-team decisions.
- Attack-family labels.
- Post-settlement information.
- Any simulation-only field.

---

## 3. Provenance Metadata

Every major entity should contain:

```python
class Provenance(BaseModel):
    source_type: str
    source_id: str | None = None
    source_dataset: str | None = None
    source_version: str | None = None

    generator_name: str | None = None
    generator_version: str | None = None
    seed: int | None = None

    availability: str
    created_at: datetime
```

Example:

```json
{
  "source_type": "synthetic",
  "source_dataset": "fraudforge_behavior_simulator",
  "source_version": "0.1.0",
  "generator_name": "mule_network_v1",
  "generator_version": "1.0",
  "seed": 42,
  "availability": "at_authorization",
  "created_at": "2026-08-17T10:00:00Z"
}
```

---

## 4. Entity Types

The platform uses these entity types:

```text
Customer
Account
PaymentInstrument
Merchant
Beneficiary
Device
IPNetwork
Location
Agent
Tool
Intent
Transaction
Threat
AttackSpecification
NetworkEdge
SimulationEvent
RiskDecision
EvaluationResult
BlueTeamReport
```

---

## 5. Common Entity Fields

```python
class EntityBase(BaseModel):
    entity_id: str
    entity_type: str
    status: str = "active"

    provenance: Provenance
    created_at: datetime
    updated_at: datetime
```

All entity identifiers must be synthetic or pseudonymous.

Do not store:

- Real PANs.
- Real bank-account numbers.
- Real Aadhaar numbers.
- Real phone numbers.
- Real email addresses.
- Raw credentials.
- Production API keys.

---

## 6. Customer

A Customer represents a synthetic or pseudonymous payer.

```python
class Customer(EntityBase):
    entity_type: Literal["customer"] = "customer"

    country: str
    region: str | None = None
    customer_segment: str

    account_age_days: int
    onboarding_channel: str

    preferred_currency: str
    risk_profile: str = "unknown"

    historical_average_amount: float = 0.0
    historical_transaction_count: int = 0
    historical_merchant_count: int = 0
    historical_beneficiary_count: int = 0

    identity_risk_score: float = 0.0
    customer_behavior_score: float = 0.0
```

### Available at authorization

```text
customer_id
country
region
account_age_days
historical transaction aggregates
identity risk
behavioral baseline
```

### Usually unavailable or restricted

```text
real name
real address
raw identity document
full cross-bank customer history
```

---

## 7. Account

An Account represents a payment or banking account.

```python
class Account(EntityBase):
    entity_type: Literal["account"] = "account"

    customer_id: str
    account_type: str
    currency: str
    country: str

    opened_at: datetime
    account_status: str = "active"

    authentication_level: str
    account_risk_score: float = 0.0

    device_count_30d: int = 0
    ip_count_30d: int = 0
    beneficiary_count_30d: int = 0
```

Relationships:

```text
Customer → Account
Account → PaymentInstrument
Account → Device
Account → IPNetwork
Account → Merchant
Account → Beneficiary
Account → Transaction
```

---

## 8. Payment Instrument

A PaymentInstrument represents a synthetic card, wallet, or payment token.

```python
class PaymentInstrument(EntityBase):
    entity_type: Literal["payment_instrument"] = "payment_instrument"

    account_id: str
    instrument_type: str
    payment_rail: str
    issuer_country: str

    tokenized: bool = True
    issued_at: datetime
    status: str = "active"

    instrument_risk_score: float = 0.0
    testing_attempt_count_24h: int = 0
```

Allowed `instrument_type` values:

```text
synthetic_card
network_token
wallet_token
bank_account_token
upi_handle_token
```

Never store real payment credentials.

---

## 9. Merchant

```python
class Merchant(EntityBase):
    entity_type: Literal["merchant"] = "merchant"

    merchant_category: str
    country: str
    region: str | None = None

    onboarding_date: datetime
    merchant_status: str = "active"

    website_risk_score: float = 0.0
    merchant_risk_score: float = 0.0

    transaction_count_30d: int = 0
    chargeback_rate_30d: float = 0.0
    refund_rate_30d: float = 0.0

    settlement_account_id: str | None = None
```

The merchant model should support:

- Legitimate merchants.
- Fraudulent merchants.
- Merchant collusion.
- Merchant impersonation.
- Merchant substitution.

---

## 10. Beneficiary

A Beneficiary is the destination of a payment.

```python
class Beneficiary(EntityBase):
    entity_type: Literal["beneficiary"] = "beneficiary"

    beneficiary_type: str
    country: str
    currency: str

    created_at: datetime
    status: str = "active"

    account_age_days: int = 0
    sender_count_7d: int = 0
    sender_count_30d: int = 0
    incoming_amount_7d: float = 0.0
    outgoing_amount_7d: float = 0.0

    mule_risk_score: float = 0.0
    beneficiary_risk_score: float = 0.0
```

Useful beneficiary types:

```text
merchant
customer
business
wallet
mule_account
synthetic_recipient
agent_destination
```

---

## 11. Device

```python
class Device(EntityBase):
    entity_type: Literal["device"] = "device"

    device_class: str
    operating_system: str
    browser_family: str | None = None

    first_seen_at: datetime
    last_seen_at: datetime

    account_count_7d: int = 0
    account_count_30d: int = 0
    customer_count_30d: int = 0

    emulator_risk_score: float = 0.0
    device_risk_score: float = 0.0
```

Do not store raw device fingerprints. Use synthetic or hashed identifiers.

---

## 12. IP Network

```python
class IPNetwork(EntityBase):
    entity_type: Literal["ip_network"] = "ip_network"

    network_type: str
    country: str
    region: str | None = None

    first_seen_at: datetime
    last_seen_at: datetime

    account_count_24h: int = 0
    account_count_7d: int = 0
    device_count_7d: int = 0

    proxy_risk_score: float = 0.0
    network_risk_score: float = 0.0
```

Use categories instead of real IPs:

```text
residential
mobile_carrier
corporate_nat
public_wifi
datacenter
proxy
vpn
synthetic_network
```

---

## 13. Location

```python
class Location(EntityBase):
    entity_type: Literal["location"] = "location"

    country: str
    region: str | None = None
    city_class: str | None = None
    latitude_bucket: str | None = None
    longitude_bucket: str | None = None

    location_risk_score: float = 0.0
```

Use coarse locations or synthetic regions to avoid exposing real personal locations.

---

## 14. Agent

An Agent represents an AI or automated actor that may act on behalf of a customer.

```python
class Agent(EntityBase):
    entity_type: Literal["agent"] = "agent"

    owner_customer_id: str | None = None
    owner_account_id: str | None = None

    agent_type: str
    provider: str | None = None
    version: str | None = None

    identity_status: str
    attestation_status: str
    created_at: datetime
    expires_at: datetime | None = None

    approved_tool_count: int = 0
    transaction_count_24h: int = 0
    out_of_scope_attempt_count_30d: int = 0

    agent_behavior_score: float = 0.0
    agent_risk_score: float = 0.0
```

Allowed `identity_status` values:

```text
unknown
unverified
verified
revoked
expired
compromised
```

---

## 15. Tool

A Tool represents an external capability called by an agent.

```python
class Tool(EntityBase):
    entity_type: Literal["tool"] = "tool"

    provider: str
    tool_type: str
    version: str | None = None

    trust_status: str
    manifest_hash: str | None = None
    allowed_operations: list[str] = []

    used_by_agent_count_7d: int = 0
    tool_risk_score: float = 0.0
```

Allowed trust states:

```text
approved
unknown
suspended
revoked
compromised
```

The tool model is essential for simulating:

- Tool hijacking.
- Malicious merchant responses.
- Indirect prompt injection.
- Tool-provenance gaps.

---

## 16. Intent

Intent represents the user’s authorized purpose and constraints.

```python
class Intent(EntityBase):
    entity_type: Literal["intent"] = "intent"

    customer_id: str
    account_id: str
    agent_id: str

    created_at: datetime
    expires_at: datetime | None = None
    status: str = "active"

    purpose: str
    max_amount: float | None = None
    cumulative_amount_limit: float | None = None
    cumulative_amount_used: float = 0.0

    currency: str
    allowed_merchants: list[str] = []
    allowed_categories: list[str] = []
    allowed_countries: list[str] = []
    allowed_beneficiaries: list[str] = []

    approval_required_above: float | None = None

    signature_status: str = "synthetic_valid"
    provenance_status: str = "complete"
```

Intent fields allow the system to detect:

```text
amount violation
merchant violation
category violation
country violation
beneficiary violation
cumulative spend violation
expired intent
missing intent
invalid provenance
```

---

## 17. Transaction

The Transaction is the primary payment object.

```python
class Transaction(EntityBase):
    entity_type: Literal["transaction"] = "transaction"

    timestamp: datetime

    customer_id: str
    account_id: str
    payment_instrument_id: str | None = None

    merchant_id: str | None = None
    beneficiary_id: str | None = None

    device_id: str | None = None
    ip_network_id: str | None = None
    location_id: str | None = None

    agent_id: str | None = None
    intent_id: str | None = None
    tool_id: str | None = None

    amount: float
    currency: str
    payment_rail: str
    transaction_type: str
    merchant_category: str | None = None

    authentication_method: str
    authentication_result: str

    transaction_status: str = "initiated"

    # Authorization-time derived values
    customer_txn_count_1h: int = 0
    customer_txn_count_24h: int = 0
    customer_amount_24h: float = 0.0

    merchant_txn_count_24h: int = 0
    beneficiary_sender_count_7d: int = 0
    device_account_count_7d: int = 0
    ip_account_count_7d: int = 0

    amount_deviation_score: float = 0.0
    behavior_deviation_score: float = 0.0
    network_risk_score: float = 0.0
    intent_risk_score: float = 0.0
    agent_risk_score: float = 0.0

    # Ground truth and simulation metadata
    is_fraud: int | None = None
    attack_family: str | None = None
    attack_instance_id: str | None = None
```

The fields below must never be model inputs:

```text
is_fraud
attack_family
attack_instance_id
transaction_status if it represents a post-decision outcome
chargeback outcome
confirmed fraud outcome
```

---

## 18. Transaction Status

Allowed transaction states:

```text
created
intent_checked
payment_prepared
risk_scoring
review_required
approved
blocked
settlement_simulated
reversed_simulated
```

Allowed transitions:

```text
created → intent_checked
intent_checked → payment_prepared
payment_prepared → risk_scoring
risk_scoring → review_required
risk_scoring → approved
risk_scoring → blocked
approved → settlement_simulated
settlement_simulated → reversed_simulated
```

A blocked transaction cannot transition directly to settlement.

---

## 19. Network Edge

Every relationship in the payment graph is represented as an edge.

```python
class NetworkEdge(EntityBase):
    entity_type: Literal["network_edge"] = "network_edge"

    source_id: str
    source_type: str
    target_id: str
    target_type: str

    relation: str
    first_seen_at: datetime
    last_seen_at: datetime

    interaction_count: int = 1
    amount_total: float = 0.0
    amount_average: float = 0.0

    edge_status: str = "active"
    edge_risk_score: float = 0.0

    created_by_event_id: str | None = None
```

Allowed relations:

```text
owns
uses
logs_in_from
pays
sends_to
receives_from
initiates
authorized_by
uses_tool
contacts
settles_to
shares_device
shares_ip
belongs_to_cluster
```

Example:

```json
{
  "source_id": "account_019",
  "source_type": "account",
  "target_id": "beneficiary_991",
  "target_type": "beneficiary",
  "relation": "sends_to",
  "first_seen_at": "2026-08-17T09:00:00Z",
  "last_seen_at": "2026-08-17T09:10:00Z",
  "interaction_count": 3,
  "amount_total": 79500,
  "edge_risk_score": 0.81
}
```

---

## 20. Fraud Cluster

A FraudCluster represents a group of related entities or transactions.

```python
class FraudCluster(EntityBase):
    entity_type: Literal["fraud_cluster"] = "fraud_cluster"

    cluster_type: str
    member_entity_ids: list[str]
    member_transaction_ids: list[str]

    created_at: datetime
    detected_at: datetime | None = None

    cluster_size: int
    edge_count: int
    community_score: float = 0.0
    concentration_score: float = 0.0
    temporal_coordination_score: float = 0.0
    cluster_risk_score: float = 0.0

    cluster_status: str = "candidate"
```

Cluster types:

```text
mule_ring
shared_device_ring
shared_ip_ring
beneficiary_cluster
merchant_cluster
agent_coordination_cluster
account_takeover_cluster
```

---

## 21. Threat Record Reference

The full Threat Record is defined in:

```text
docs/THREAT_LIBRARY_SPEC.md
```

The data model should reference the threat using:

```python
class ThreatReference(BaseModel):
    threat_id: str
    version: str
    historical_status: str
    source_ids: list[str]
```

---

## 22. Attack Specification

An AttackSpecification is an approved, executable red-team plan.

```python
class AttackSpecification(EntityBase):
    entity_type: Literal["attack_specification"] = "attack_specification"

    threat_id: str
    threat_version: str

    generation_mode: str
    attack_family: str
    secondary_patterns: list[str] = []

    payment_rail: str
    geography: str
    target_population: str

    scale: int
    seed: int

    transaction_plan: dict
    network_plan: dict
    agent_plan: dict
    intent_plan: dict
    evasion_plan: dict

    expected_signals: list[str]
    expected_mitigations: list[str]

    novelty_score: float = 0.0
    fidelity_target: float | None = None

    validation_status: str = "pending"
    safety_status: str = "simulation_only"
```

Allowed `generation_mode` values:

```text
replay
mutation
composition
adaptive_variant
```

---

## 23. Attack Hypothesis

An AttackHypothesis is a reasoning output and is not yet executable.

```python
class AttackHypothesis(EntityBase):
    entity_type: Literal["attack_hypothesis"] = "attack_hypothesis"

    title: str
    primary_family: str
    secondary_patterns: list[str]

    attacker_types: list[str]
    objective: list[str]
    target_surfaces: list[str]

    historical_basis: list[str]
    reasoning_summary: str
    novelty_claim: str

    attack_sequence: list[dict]
    graph_motif: dict
    payment_behavior: dict
    network_behavior: dict
    agent_behavior: dict
    intent_behavior: dict

    expected_signals: list[str]
    evasion_strategy: list[str]

    simulator_templates: list[str]
    required_capabilities: list[str]

    semantic_novelty: float = 0.0
    sequence_novelty: float = 0.0
    graph_novelty: float = 0.0
    behavior_novelty: float = 0.0
    overall_novelty: float = 0.0

    validation_status: str = "pending"
    safety_status: str = "simulation_only"
```

---

## 24. Simulation Event

The SimulationEvent records the lifecycle of an attack or payment.

```python
class SimulationEvent(EntityBase):
    entity_type: Literal["simulation_event"] = "simulation_event"

    simulation_id: str
    sequence_number: int
    timestamp: datetime

    stage: str
    event_type: str

    actor_id: str | None = None
    actor_type: str | None = None

    customer_id: str | None = None
    account_id: str | None = None
    agent_id: str | None = None
    tool_id: str | None = None
    intent_id: str | None = None
    transaction_id: str | None = None
    merchant_id: str | None = None
    beneficiary_id: str | None = None

    payload: dict = {}
    risk_signals: dict = {}

    event_status: str = "generated"
```

Allowed lifecycle stages:

```text
reconnaissance
social_engineering
identity_compromise
agent_manipulation
payment_preparation
payment_initiation
authorization
intervention
settlement
learning
```

Allowed event types:

```text
profile_observed
communication_created
login_attempt
device_registered
credential_change
intent_created
tool_called
tool_output_received
payment_parameter_changed
beneficiary_added
payment_requested
risk_scored
policy_checked
payment_approved
payment_reviewed
payment_blocked
settlement_simulated
cashout_simulated
hard_negative_created
model_retrained
```

---

## 25. Risk Score

All model and policy components should produce separate scores.

```python
class RiskScore(BaseModel):
    transaction_risk: float = 0.0
    behavior_risk: float = 0.0
    device_risk: float = 0.0
    identity_risk: float = 0.0
    network_risk: float = 0.0
    intent_risk: float = 0.0
    agent_risk: float = 0.0
    anomaly_score: float = 0.0

    combined_score: float = 0.0
    model_version: str
    scored_at: datetime
```

All values must be between 0 and 1.

---

## 26. Risk Decision

```python
class RiskDecision(EntityBase):
    entity_type: Literal["risk_decision"] = "risk_decision"

    transaction_id: str
    simulation_id: str | None = None

    decision: str
    recommended_action: str

    risk_score: RiskScore

    threshold_review: float
    threshold_block: float

    reason_codes: list[str]
    policy_results: list[dict]

    model_version: str
    policy_version: str

    decision_latency_ms: float | None = None
```

Allowed decisions:

```text
ALLOW
REVIEW
BLOCK
```

Allowed actions:

```text
approve
approve_with_monitoring
step_up
manual_review
hold_settlement
block_payment
revoke_agent
revoke_tool
freeze_beneficiary
```

---

## 27. Reason Codes

Reason codes should be human-readable and machine-readable.

```python
REASON_CODES = {
    "new_device": "New device for this account",
    "high_device_account_degree": "Device is associated with many accounts",
    "new_beneficiary": "Beneficiary has not been used previously",
    "beneficiary_concentration": "Many accounts send funds to this beneficiary",
    "unusual_velocity": "Transaction frequency is above the customer baseline",
    "amount_deviation": "Amount differs significantly from historical behavior",
    "intent_destination_mismatch": "Payment destination differs from authorized intent",
    "intent_amount_violation": "Payment exceeds the authorized amount",
    "intent_expired": "Payment intent has expired",
    "agent_behavior_drift": "Agent behavior differs from its historical baseline",
    "tool_provenance_gap": "Tool provenance could not be verified",
    "shared_infrastructure": "Account shares infrastructure with suspicious entities",
}
```

---

## 28. Ground Truth

Ground truth is separate from model output.

```python
class GroundTruth(BaseModel):
    is_fraud: int
    fraud_family: str
    attack_instance_id: str | None = None
    attack_stage: str | None = None

    expected_decision: str
    expected_signals: list[str]
    expected_impact: float | None = None

    source_type: str
    confidence: float
```

Ground truth may be:

```text
historical_label
synthetic_label
simulated_attack_label
expert_review
```

The model must not receive ground-truth fields during inference.

---

## 29. Blue-Team Report

```python
class BlueTeamReport(EntityBase):
    entity_type: Literal["blue_team_report"] = "blue_team_report"

    attack_run_id: str
    model_version: str
    policy_version: str

    transactions_generated: int
    transactions_valid: int
    detected_count: int
    missed_count: int

    bypass_rate: float
    precision: float
    recall: float
    f1: float
    pr_auc: float
    false_positive_rate: float

    weak_signal_groups: list[str]
    missed_features: list[str]
    strong_features: list[str]

    network_findings: list[str]
    agent_findings: list[str]
    intent_findings: list[str]

    red_team_next_directions: list[str]
    blue_team_recommendations: list[str]

    report_status: str = "generated"
```

---

## 30. Loop Intelligence Report

```python
class LoopIntelligenceReport(EntityBase):
    entity_type: Literal["loop_intelligence_report"] = "loop_intelligence_report"

    attack_run_id: str

    red_team_learning: dict
    blue_team_learning: dict

    attack_variants_to_generate: list[dict]
    features_to_add: list[str]
    policies_to_update: list[str]

    bypass_before: float
    bypass_after: float | None = None

    model_version_before: str
    model_version_after: str | None = None

    retraining_required: bool
    next_iteration_status: str
```

---

## 31. Feature Registry

Every model feature must be registered.

```python
class FeatureDefinition(BaseModel):
    feature_name: str
    description: str
    data_type: str

    source_entities: list[str]
    computation_method: str

    availability: str
    allowed_for_authorization: bool

    leakage_risk: str
    privacy_class: str
```

Example:

```yaml
feature_name: beneficiary_sender_count_7d
description: Number of distinct accounts that sent money to the beneficiary in the previous seven days.
data_type: integer
source_entities:
  - transaction
  - beneficiary
  - account
computation_method: distinct_sender_count_before_event
availability: at_authorization
allowed_for_authorization: true
leakage_risk: low
privacy_class: pseudonymous_derived
```

Forbidden example:

```yaml
feature_name: confirmed_fraud_label
availability: post_event_only
allowed_for_authorization: false
leakage_risk: critical
```

---

## 32. Model Input Contract

The Blue Team model receives:

```python
class ModelInput(BaseModel):
    transaction_features: dict
    behavior_features: dict
    network_features: dict
    identity_features: dict
    intent_features: dict
    agent_features: dict
```

The model input must not contain:

```text
is_fraud
attack_family
attack_instance_id
expected_decision
chargeback_result
blue_team_decision
future_transaction_count
post_event_investigation
```

---

## 33. Simulation Run

```python
class SimulationRun(EntityBase):
    entity_type: Literal["simulation_run"] = "simulation_run"

    attack_specification_id: str
    simulator_version: str
    compiler_version: str
    seed: int

    started_at: datetime
    completed_at: datetime | None = None

    transactions_generated: int = 0
    events_generated: int = 0
    network_edges_generated: int = 0

    validity_rate: float = 0.0
    transaction_fidelity_score: float = 0.0
    network_fidelity_score: float = 0.0
    temporal_fidelity_score: float = 0.0

    status: str = "created"
```

---

## 34. Data Relationships

```text
Customer
  └── Account
        ├── PaymentInstrument
        ├── Device
        ├── IPNetwork
        ├── Intent
        └── Transaction

Merchant
  ├── Transaction
  ├── Tool
  └── Beneficiary

Agent
  ├── Intent
  ├── Tool
  └── Transaction

Transaction
  ├── RiskDecision
  ├── SimulationEvent
  └── GroundTruth

ThreatRecord
  ├── AttackHypothesis
  ├── AttackSpecification
  └── SimulationRun

SimulationRun
  ├── Transactions
  ├── NetworkEdges
  ├── SimulationEvents
  ├── RiskDecisions
  └── BlueTeamReport

BlueTeamReport
  └── LoopIntelligenceReport
```

---

## 35. Minimal Database Tables

For the first implementation, create these tables:

```text
customers
accounts
payment_instruments
merchants
beneficiaries
devices
ip_networks
agents
tools
intents
transactions
network_edges
simulation_events
threat_records
attack_hypotheses
attack_specifications
simulation_runs
risk_decisions
blue_team_reports
loop_reports
```

Do not create separate tables for every feature. Store derived features in a feature table or feature parquet file.

---

## 36. Minimal P0 Tables

For P0, implement only:

```text
customers
accounts
merchants
devices
beneficiaries
transactions
network_edges
risk_decisions
simulation_runs
```

Add these in P1:

```text
agents
tools
intents
simulation_events
attack_hypotheses
attack_specifications
```

Add these in P2/P3:

```text
fraud_clusters
blue_team_reports
loop_reports
model_versions
feature_registry
```

---

## 37. Data Storage Formats

Use:

```text
Parquet:
large transaction and event datasets

JSON:
threat records, attack specifications, reports

SQLite or PostgreSQL:
entities, relationships, experiment metadata

PNG/HTML:
charts and evaluation artifacts

Pickle/joblib:
only trusted local model artifacts
```

Recommended layout:

```text
backend/data/
├── raw/
├── processed/
├── simulations/
├── artifacts/
├── reports/
└── manifests/
```

---

## 38. Run Manifest

Every experiment must produce a run manifest.

```json
{
  "run_id": "RUN-0001",
  "phase": "P0",
  "seed": 42,
  "source_dataset": "ulb_credit_card",
  "source_version": "public",
  "simulator_version": "0.1.0",
  "compiler_version": "0.1.0",
  "threat_library_version": "0.1.0",
  "model_version": "BLUE-0.1.0",
  "feature_manifest": "features-v1.json",
  "rows_generated": 100000,
  "fraud_rate": 0.025,
  "status": "completed"
}
```

---

## 39. Data Validation Rules

### Transaction rules

- Amount must be greater than zero.
- Currency must be supported.
- Timestamp must be valid.
- Customer and account must exist.
- Beneficiary must exist before payment.
- Agent must exist before agent-initiated payment.
- Intent must exist before intent-scoped payment.
- Payment rail must support the transaction type.

### Relationship rules

- Edge source and target must exist.
- First-seen time must be before last-seen time.
- Edge cannot reference a future entity.
- Transaction edge timestamp must match transaction timestamp.
- Settlement edges cannot exist before authorization.

### Ground-truth rules

- Legitimate rows must have `is_fraud = 0`.
- Injected attack rows must have `is_fraud = 1`.
- Ground truth must not be used as a model input.
- Attack family must not be exposed to the detector.

---

## 40. Data Quality Tests

Required tests:

```text
ID uniqueness
Required-field completeness
Timestamp ordering
Positive amount validation
Currency validation
Entity-reference integrity
Edge-reference integrity
No future-feature leakage
No post-event feature usage
Reproducibility under fixed seed
Fraud-label consistency
Attack-template consistency
Simulation-only enforcement
```

---

## 41. Privacy and Safety

All prototype data must be:

```text
synthetic
pseudonymous
tokenized
coarse-grained
simulation-only
```

The system must not persist:

- Real payment credentials.
- Real identity documents.
- Raw phone numbers.
- Raw email addresses.
- Real bank accounts.
- Real UPI identifiers.
- Real customer communications.
- Production secrets.

---

## 42. Definition of Done

The data model is ready when the system can:

1. Create a synthetic customer and account.
2. Attach a device, IP, merchant, and beneficiary.
3. Generate a transaction.
4. Create a network edge for that transaction.
5. Derive authorization-time features.
6. Assign simulation ground truth.
7. Score the transaction.
8. Create a risk decision.
9. Store all events and provenance.
10. Replay the same run using the same seed.
11. Produce a complete run manifest.
12. Reject invalid or unsafe records.
```

# What comes next

After saving `docs/DATA_MODEL.md`, the next document is:

```
docs/ML_EVALUATION.md
```

That document will define:

- Train/validation/test splitting.
- Transaction-level metrics.
- Network-level metrics.
- Agent and intent metrics.
- Fidelity metrics.
- Novelty metrics.
- Red-team bypass rate.
- Blue-team improvement.
- Closed-loop evaluation.
- Threshold selection.
- Leakage prevention.
- Model comparison.

