# BUILD REQUEST: FraudForge - Mastercard Innovation Challenge 2026

## PROJECT OVERVIEW

Build an **end-to-end closed-loop adversarial AI system** for payment fraud detection with three pillars:

1. **IDENTIFY** - Research and generate emerging GenAI-powered payment fraud attacks
2. **GENERATE** - Create high-fidelity synthetic fraud transactions
3. **DEFEND** - Detect generated attacks accurately while keeping false positives low

This is a **Red Team/Blue Team** exercise adapted from CrowdStrike's methodology for payment fraud.

## RESEARCH FOUNDATION

This build is based on two comprehensive research documents:

### Research Document 1: "CLOSED-LOOP ADVERSARIAL AI FOR GENAI PAYMENT FRAUD"
- **30-50+ GenAI-powered payment fraud attacks** identified across 21 categories
- **8 Tier 1 attacks** selected for Red Team simulation
- **CTGAN + Rule-Based Hybrid** for high-fidelity synthetic fraud generation
- **XGBoost baseline** expected to achieve F1 >0.82
- **Intent and Agent signals** provide largest improvement (+40-45% for agentic fraud)
- **RL-based adversarial optimization** (FRAUD-RLA) enables adaptive Red Team
- **Closed-loop feedback** improves detection over iterations (attack success 35% → 8%, F1 0.82 → 0.89)

### Research Document 2: "HOW FRAUDSTERS USE AI TO COMMIT PAYMENT FRAUD"
**5 Attack Vectors to Implement:**

1. **AI Phishing → Account Takeover → Fraud**
   - LLM generates personalized phishing emails
   - Fraudster captures credentials, takes over account
   - Initiates high-value transactions from new device, unusual location, high velocity

2. **Synthetic Identity → KYC Bypass → Mule Account**
   - GAN generates fake faces, LLM generates fake identity details
   - Deepfake bypasses video KYC/liveness checks
   - Account matures with small transactions, then used for money laundering

3. **Voice Cloning → APP Scam → UPI Fraud**
   - TTS clones family member's voice (30-60 sec audio sample)
   - Fraudster calls victim: "Mom, I'm in emergency, need money"
   - Victim approves UPI collect request or sends to fraudster's UPI ID

4. **AI Agent → Unauthorized Payment → Intent Mismatch**
   - Fraudster uses prompt injection to hijack AI shopping agent
   - Agent exploits excessive permissions (delegated $1,500 limit, but has $5,000 authority)
   - Agent initiates payment to fraudulent merchant (violates constraints)

5. **Adversarial Transactions → Model Evasion → Fraud**
   - Fraudster uses RL to optimize fraud patterns
   - RL agent learns: "Keep amount <₹50K, velocity <5/hour, use new device but from same location"
   - Bypasses fraud detector (looks "normal")

## TECHNICAL REQUIREMENTS

### Tech Stack (Must Use)
- **Backend**: Python 3.10+, FastAPI
- **ML Models**: XGBoost (detector), CTGAN (synthetic fraud), Autoencoder (anomaly detection), Stable Baselines3 (RL-DQN)
- **LLM**: OpenAI GPT-4 API (for attack discovery agent, phishing generation)
- **Database**: SQLite (for hackathon)
- **Frontend**: Streamlit (for rapid prototyping)
- **Visualization**: Plotly
- **Styling**: Tailwind CSS (Mastercard colors: #EB001B red, #000000 black, #FFFFFF white)

### Dataset (Use This)
**IEEE-CIS Fraud Detection Dataset** from Kaggle:
- Link: https://www.kaggle.com/c/ieee-fraud-detection/data
- Size: 590K transactions, 3.5% fraud rate
- Features: 871 columns (transaction + identity tables)
- License: CC BY-NC-SA 4.0 (permissible for hackathon)

**Alternative (if IEEE-CIS is too large)**:
- **Credit Card Fraud Detection**: https://www.kaggle.com/mlg-ulb/creditcardfraud
- Size: 284K transactions, 0.17% fraud rate

## SYSTEM ARCHITECTURE

### RED TEAM (Attack Generation)

#### Agent 1: Fraud Research Agent (LLM + RAG)
**Purpose**: Discover emerging fraud patterns from threat intelligence
**Input**: Web search results, research papers, news articles
**Output**: List of fraud attack hypotheses (JSON format)

**Implementation**:
```python
from langchain import LLMChain
from langchain.llms import OpenAI

class FraudResearchAgent:
    def __init__(self):
        self.llm = OpenAI(temperature=0.7, model="gpt-4")
        self.prompt = """
        You are a payment fraud researcher. Based on the following threat intelligence,
        generate 5 novel GenAI-powered payment fraud attack hypotheses.
        
        Threat Intelligence:
        {threat_intel}
        
        Attack Types to Consider:
        1. AI Phishing → Account Takeover → High-Value Purchase
        2. Synthetic Identity → KYC Bypass → Mule Account
        3. Voice Cloning → APP Scam → UPI Fraud
        4. AI Agent → Unauthorized Payment → Intent Mismatch
        5. Adversarial Transactions → Model Evasion
        
        Output format (JSON):
        [
            {{
                "hypothesis_id": "HYP-001",
                "attack_name": "AI Phishing → Account Takeover",
                "attack_surface": "Email + Login + Transaction",
                "ai_component": "LLM-generated personalized phishing",
                "payment_impact": "Unauthorized high-value purchase",
                "detectable_signals": ["device_change", "velocity_spike", "location_anomaly"],
                "owasp_mapping": ["LLM01: Prompt Injection"],
                "confidence_score": 0.85
            }}
        ]
        """
    
    def generate_hypotheses(self, threat_intel: str) -> list:
        chain = LLMChain(llm=self.llm, prompt=self.prompt)
        response = chain.run(threat_intel=threat_intel)
        return json.loads(response)
```

**Test Scenario**:
```python
threat_intel = """
Recent reports show:
1. AI phishing scams targeting bank customers (Feb 2026)
2. Deepfake voice scams impersonating family members (Jan 2026)
3. Synthetic identity fraud up 2137% since 2022
4. Mastercard Agent Pay launched with 35+ partners (June 2026)
"""

hypotheses = agent.generate_hypotheses(threat_intel)
assert len(hypotheses) == 5
assert "hypothesis_id" in hypotheses
assert "detectable_signals" in hypotheses
```

---

#### Agent 2: Attack Generator (CTGAN + Rule-Based Mutation)
**Purpose**: Generate synthetic fraud transactions at scale with high fidelity
**Input**: Real fraud samples from IEEE-CIS dataset, attack hypotheses
**Output**: Synthetic fraud transactions (tabular data)

**Implementation**:
```python
from sdv.tabular import CTGAN
import pandas as pd
import numpy as np

class AttackGenerator:
    def __init__(self, fraud_samples: pd.DataFrame):
        """
        fraud_samples: DataFrame with only fraudulent transactions (isFraud=1)
        """
        self.ctgan = CTGAN(
            embedding_dim=10,
            generator_dim=(256, 256),
            discriminator_dim=(256, 256),
            batch_size=500,
            epochs=100
        )
        self.fraud_samples = fraud_samples
    
    def train(self):
        """Train CTGAN on real fraud samples"""
        self.ctgan.fit(self.fraud_samples)
    
    def generate_synthetic_fraud(self, n_samples: int = 10000, attack_type: str = "AI_Phishing_ATO") -> pd.DataFrame:
        """Generate synthetic fraud transactions"""
        synthetic_fraud = self.ctgan.sample(n_samples)
        
        # Add attack metadata
        synthetic_fraud['attack_family'] = attack_type
        synthetic_fraud['attack_generation_method'] = 'CTGAN'
        
        return synthetic_fraud
    
    def mutate_for_attack_vector(self, base_transaction: pd.Series, attack_type: str) -> pd.Series:
        """Apply rule-based mutation for specific attack vector"""
        mutated = base_transaction.copy()
        
        if attack_type == "AI_Phishing_ATO":
            # Account Takeover: new device, unusual location, high velocity, high amount
            mutated['device_change'] = 1
            mutated['location_deviation'] = np.random.uniform(3.0, 5.0)  # High deviation
            mutated['velocity_1h'] = np.random.randint(6, 10)  # High velocity
            mutated['TransactionAmt'] = np.random.uniform(15000, 50000)  # High amount
            mutated['time_of_day'] = np.random.choice(['night', 'early_morning'])  # Unusual time
            
        elif attack_type == "Synthetic_Identity":
            # Synthetic Identity: new account, no history, maturing with small transactions
            mutated['account_age_days'] = np.random.randint(1, 30)  # New account
            mutated['historical_spend_avg'] = 0  # No history
            mutated['TransactionAmt'] = np.random.uniform(500, 2000)  # Small transactions (maturing)
            
        elif attack_type == "AI_Agent_Intent_Mismatch":
            # AI Agent: intent constraint violation
            mutated['agent_id'] = 'ShoppingAssistant_AI'
            mutated['intent_id'] = 'INTENT-001'
            mutated['delegated_amount_limit'] = 1500  # $1,500 limit
            mutated['TransactionAmt'] = np.random.uniform(2000, 3000)  # Exceeds limit
            mutated['amount_constraint_violation'] = 1
            mutated['merchant_constraint_violation'] = 1
            
        elif attack_type == "Adversarial_Transaction":
            # Adversarial: subtle perturbations to evade detection
            mutated['TransactionAmt'] = base_transaction['TransactionAmt'] * np.random.uniform(0.85, 1.15)  # ±15%
            mutated['velocity_1h'] = max(1, base_transaction['velocity_1h'] + np.random.randint(-2, 2))  # Small change
            
        return mutated
    
    def evaluate_fidelity(self, synthetic: pd.DataFrame, real: pd.DataFrame) -> dict:
        """Evaluate how realistic synthetic fraud is"""
        from scipy import stats
        
        # Compare distributions (Kolmogorov-Smirnov test)
        ks_tests = {}
        for col in ['TransactionAmt', 'velocity_1h']:  # Use numeric columns
            if col in synthetic.columns and col in real.columns:
                ks_stat, p_value = stats.ks_2samp(synthetic[col], real[col])
                ks_tests[col] = {'ks_statistic': ks_stat, 'p_value': p_value}
        
        # Calculate Attack Fidelity Score (AFS)
        ks_avg = np.mean([v['ks_statistic'] for v in ks_tests.values()])
        afs = (1 - ks_avg) * 100
        
        return {
            'ks_tests': ks_tests,
            'attack_fidelity_score': afs,
            'synthetic_shape': synthetic.shape,
            'real_shape': real.shape
        }
```

**Test Scenario**:
```python
# Load IEEE-CIS fraud samples
fraud_data = pd.read_csv('train_transaction.csv')
fraud_samples = fraud_data[fraud_data['isFraud'] == 1].head(10000)  # Use 10K for speed

# Train CTGAN
generator = AttackGenerator(fraud_samples)
generator.train()

# Generate synthetic fraud for each attack type
attack_types = [
    "AI_Phishing_ATO",
    "Synthetic_Identity",
    "Voice_Cloning_UPI",
    "AI_Agent_Intent_Mismatch",
    "Adversarial_Transaction"
]

all_synthetic = []
for attack_type in attack_types:
    synthetic = generator.generate_synthetic_fraud(n_samples=2000, attack_type=attack_type)
    all_synthetic.append(synthetic)

synthetic_fraud = pd.concat(all_synthetic, ignore_index=True)

# Evaluate fidelity
fidelity = generator.evaluate_fidelity(synthetic_fraud, fraud_samples)
print(f"Attack Fidelity Score: {fidelity['attack_fidelity_score']:.1f}")
# Expected: AFS > 80 (high fidelity)
assert fidelity['attack_fidelity_score'] > 80
```

---

#### Agent 3: Adversarial Optimizer (RL-DQN)
**Purpose**: Optimize synthetic fraud to evade detection (maximize fraud success, minimize detection)
**Input**: Synthetic fraud transactions, fraud detector scores
**Output**: Adversarial transactions (optimized to evade detection)

**Implementation**:
```python
import numpy as np
import gym
from stable_baselines3 import DQN
import torch
import torch.nn as nn

class FraudEnv(gym.Env):
    """RL environment for adversarial fraud generation"""
    
    def __init__(self, synthetic_fraud: pd.DataFrame, detector_model):
        super().__init__()
        self.synthetic_fraud = synthetic_fraud.values
        self.detector = detector_model
        self.n_features = synthetic_fraud.shape[1]
        
        # Action space: perturb each feature by -15% to +15%
        self.action_space = gym.spaces.Box(
            low=-0.15, high=0.15, shape=(self.n_features,), dtype=np.float32
        )
        
        # State space: current transaction features
        self.observation_space = gym.spaces.Box(
            low=-np.inf, high=np.inf, shape=(self.n_features,), dtype=np.float32
        )
        
        self.current_idx = 0
        self.current_transaction = None
    
    def reset(self):
        self.current_idx = 0
        self.current_transaction = self.synthetic_fraud[self.current_idx]
        return self.current_transaction.astype(np.float32)
    
    def step(self, action):
        # Perturb transaction
        perturbed = self.current_transaction * (1 + action)
        
        # Get fraud score from detector
        fraud_prob = self.detector.predict_proba([perturbed])[1]
        
        # Reward: high fraud amount - detection score (penalize detection)
        fraud_amount = perturbed if len(perturbed) > 0 else 1000  # Assuming first column is amount
        reward = fraud_amount - (fraud_prob * 1000)  # Penalize detection
        
        # Move to next transaction
        self.current_idx += 1
        if self.current_idx < len(self.synthetic_fraud):
            self.current_transaction = self.synthetic_fraud[self.current_idx]
            done = False
        else:
            done = True
        
        return perturbed.astype(np.float32), reward, done, {}

class AdversarialOptimizer:
    def __init__(self, synthetic_fraud: pd.DataFrame, detector_model):
        self.env = FraudEnv(synthetic_fraud, detector_model)
        self.model = DQN("MlpPolicy", self.env, verbose=1, learning_rate=0.001)
    
    def train(self, timesteps: int = 10000):
        """Train RL agent to optimize adversarial attacks"""
        self.model.learn(total_timesteps=timesteps)
    
    def generate_adversarial_attacks(self, n_attacks: int = 100) -> np.ndarray:
        """Generate optimized adversarial transactions"""
        adversarial = []
        for _ in range(n_attacks):
            obs = self.env.reset()
            action, _ = self.model.predict(obs)
            adversarial.append(action)
        return np.array(adversarial)
    
    def evaluate_attack_success(self, adversarial_attacks: np.ndarray, threshold: float = 0.5) -> dict:
        """Evaluate how many attacks bypass detection"""
        fraud_scores = self.detector.predict_proba(adversarial_attacks)[:, 1]
        
        attack_success = fraud_scores < threshold
        success_rate = attack_success.mean()
        
        return {
            'attack_success_rate': success_rate,
            'attacks_detected': (~attack_success).sum(),
            'attacks_bypassed': attack_success.sum(),
            'total_attacks': len(adversarial_attacks)
        }
```

**Test Scenario**:
```python
# Train detector first (see BLUE TEAM section)
detector = FraudDetector()
detector.train(X_train, y_train)

# Initialize adversarial optimizer
optimizer = AdversarialOptimizer(synthetic_fraud.values, detector)

# Train RL agent
optimizer.train(timesteps=10000)

# Generate adversarial attacks
adversarial_attacks = optimizer.generate_adversarial_attacks(n_attacks=100)

# Evaluate attack success rate
attack_success = optimizer.evaluate_attack_success(adversarial_attacks)
print(f"Attack Success Rate: {attack_success['attack_success_rate']:.2%}")
# Expected: 30-40% initially (before detector retraining)
assert attack_success['attack_success_rate'] > 0.30
```

---

### BLUE TEAM (Detection)

#### Agent 1: Fraud Detector (XGBoost) with Incremental Intelligence Layers
**Purpose**: Classify transactions as fraud/legitimate with progressive intelligence layers
**Input**: Transaction features (real + synthetic)
**Output**: Fraud probability (0-1), risk score (0-100), SHAP explanations

**Implementation**:
```python
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import f1_score, precision_score, recall_score, roc_auc_score
import shap

class FraudDetector:
    def __init__(self):
        self.model = xgb.XGBClassifier(
            max_depth=6,
            learning_rate=0.1,
            n_estimators=200,
            subsample=0.8,
            colsample_bytree=0.8,
            scale_pos_weight=28,  # Handle class imbalance (1/0.035 ≈ 28)
            eval_metric='logloss',
            random_state=42
        )
        self.shap_explainer = None
        self.intelligence_layer = 'V0'  # V0, V1, V4, V5
    
    def add_behavioral_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """V1: Add behavioral intelligence features"""
        df = df.copy()
        
        # Spending deviation
        df['spending_deviation'] = (df['TransactionAmt'] - df['historical_spend_avg']) / (df['historical_spend_std'] + 1)
        
        # Merchant deviation (simplified: 1 if merchant not in top 10, else 0)
        df['merchant_deviation'] = df['ProductCD'].apply(lambda x: 1 if x > 10 else 0)
        
        # Time deviation (simplified: 1 if night/early_morning, else 0)
        df['time_deviation'] = df['time_of_day'].apply(lambda x: 1 if x in ['night', 'early_morning'] else 0)
        
        # Location deviation (already in dataset as DistR1, DistR2)
        df['location_deviation'] = df['DistR1']
        
        # Velocity anomaly (Z-score)
        df['velocity_anomaly'] = (df['velocity_1h'] - df['velocity_1h'].mean()) / (df['velocity_1h'].std() + 1)
        
        return df
    
    def add_intent_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """V4: Add intent intelligence features"""
        df = df.copy()
        
        # Amount constraint violation
        df['amount_constraint_violation'] = (df['TransactionAmt'] > df['delegated_amount_limit']).astype(int)
        
        # Merchant constraint violation (simplified: 1 if merchant not on allowlist)
        df['merchant_constraint_violation'] = df['merchant_constraint_violation'].fillna(0)
        
        # Time constraint violation
        df['time_constraint_violation'] = df['time_constraint_violation'].fillna(0)
        
        # Delegation chain validity
        df['delegation_chain_valid'] = df['delegation_chain_valid'].fillna(1)
        
        # Agent ID (one-hot encode)
        if 'agent_id' in df.columns:
            df = pd.get_dummies(df, columns=['agent_id'], prefix='agent')
        
        # Intent ID (one-hot encode)
        if 'intent_id' in df.columns:
            df = pd.get_dummies(df, columns=['intent_id'], prefix='intent')
        
        return df
    
    def add_agent_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """V5: Add agent intelligence features"""
        df = df.copy()
        
        # Agent identity verified
        df['agent_identity_verified'] = df['agent_identity_verified'].fillna(1)
        
        # Agent reputation score
        df['agent_reputation_score'] = df['agent_reputation_score'].fillna(0.5)
        
        # Agent behavior anomaly (Z-score)
        df['agent_behavior_anomaly'] = df['agent_behavior_anomaly'].fillna(0)
        
        # Agent authorization scope
        df['agent_authorization_scope'] = df['agent_authorization_scope'].fillna('standard')
        
        return df
    
    def train(self, X: pd.DataFrame, y: pd.Series, intelligence_layer: str = 'V0'):
        """Train XGBoost on labeled data with specified intelligence layer"""
        self.intelligence_layer = intelligence_layer
        
        # Add features based on intelligence layer
        if intelligence_layer == 'V1':
            X = self.add_behavioral_features(X)
        elif intelligence_layer == 'V4':
            X = self.add_behavioral_features(X)
            X = self.add_intent_features(X)
        elif intelligence_layer == 'V5':
            X = self.add_behavioral_features(X)
            X = self.add_intent_features(X)
            X = self.add_agent_features(X)
        
        # Fill NaN values
        X = X.fillna(0)
        
        # Train-test split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        
        # Train model
        self.model.fit(X_train, y_train)
        
        # Evaluate
        y_pred = self.model.predict(X_test)
        y_prob = self.model.predict_proba(X_test)[:, 1]
        
        self.metrics = {
            'f1': f1_score(y_test, y_pred),
            'precision': precision_score(y_test, y_pred),
            'recall': recall_score(y_test, y_pred),
            'roc_auc': roc_auc_score(y_test, y_prob)
        }
        
        # Initialize SHAP explainer
        self.shap_explainer = shap.TreeExplainer(self.model)
        
        return self.metrics
    
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Predict fraud probability"""
        X = X.fillna(0)
        return self.model.predict_proba(X)[:, 1]
    
    def explain(self, X: pd.DataFrame, top_k: int = 5) -> pd.DataFrame:
        """Generate SHAP explanations for top features"""
        X = X.fillna(0)
        shap_values = self.shap_explainer.shap_values(X)
        
        # Get feature importance
        importance = np.abs(shap_values).mean(axis=0)
        top_features = np.argsort(importance)[-top_k:][::-1]
        
        # Create explanation DataFrame
        explanation = pd.DataFrame({
            'feature': X.columns[top_features],
            'importance': importance[top_features],
            'shap_value': shap_values[:, top_features].mean(axis=0)
        })
        
        return explanation
```

**Test Scenario**:
```python
# Load IEEE-CIS dataset
train_data = pd.read_csv('train_transaction.csv')
X = train_data.drop('isFraud', axis=1).fillna(0)
y = train_data['isFraud']

# Train detector with V0 (baseline)
detector_v0 = FraudDetector()
metrics_v0 = detector_v0.train(X, y, intelligence_layer='V0')
print(f"V0 (Baseline) - F1: {metrics_v0['f1']:.2f}, ROC-AUC: {metrics_v0['roc_auc']:.2f}")
# Expected: F1 >0.82, ROC-AUC >0.90

# Train detector with V1 (behavioral)
detector_v1 = FraudDetector()
metrics_v1 = detector_v1.train(X, y, intelligence_layer='V1')
print(f"V1 (Behavioral) - F1: {metrics_v1['f1']:.2f}, ROC-AUC: {metrics_v1['roc_auc']:.2f}")
# Expected: F1 >0.87, ROC-AUC >0.92

# Train detector with V4 (intent)
detector_v4 = FraudDetector()
metrics_v4 = detector_v4.train(X, y, intelligence_layer='V4')
print(f"V4 (Intent) - F1: {metrics_v4['f1']:.2f}, ROC-AUC: {metrics_v4['roc_auc']:.2f}")
# Expected: F1 >0.90, ROC-AUC >0.94

# Test explainability
sample_transaction = X.iloc[]
explanation = detector_v4.explain(sample_transaction, top_k=5)
print(explanation)
# Expected: Top 5 features with importance scores
```

---

#### Agent 2: Closed-Loop Orchestrator
**Purpose**: Coordinate Red Team/Blue Team, measure improvement, trigger
**Input**: Attack results, detection results
**Output**: Improvement metrics, retraining triggers

**Implementation**:
```python
class ClosedLoopOrchestrator:
    def __init__(self, red_team, blue_team):
        self.red_team = red_team
        self.blue_team = blue_team
        self.iteration = 0
        self.history = []
    
    def run_iteration(self):
        """Run one iteration of closed loop"""
        self.iteration += 1
        
        # RED TEAM: Generate attacks
        attack_hypotheses = self.red_team.research_agent.generate_hypotheses(threat_intel)
        synthetic_fraud = self.red_team.generator.generate_synthetic_fraud(n_samples=2000)
        adversarial_attacks = self.red_team.optimizer.generate_adversarial_attacks(n_attacks=100)
        
        # BLUE TEAM: Detect attacks
        fraud_scores = self.blue_team.detector.predict(adversarial_attacks)
        attack_success_rate = np.mean(fraud_scores < 0.5)
        
        # EVALUATE: Measure performance
        metrics = {
            'iteration': self.iteration,
            'attack_success_rate': attack_success_rate,
            'detection_f1': self.blue_team.detector.metrics['f1'],
            'detection_roc_auc': self.blue_team.detector.metrics['roc_auc']
        }
        self.history.append(metrics)
        
        # LEARN: If attack success rate > 10%, retrain detector
        if attack_success_rate > 0.10:
            # Add adversarial attacks to training data
            X_augmented = pd.concat([X_train, pd.DataFrame(adversarial_attacks)], ignore_index=True)
            y_augmented = pd.concat([y_train, pd.Series( * len(adversarial_attacks))], ignore_index=True)[1]
            
            # Retrain detector
            self.blue_team.detector.train(X_augmented, y_augmented)
            
            # Re-evaluate
            new_fraud_scores = self.blue_team.detector.predict(adversarial_attacks)
            new_attack_success_rate = np.mean(new_fraud_scores < 0.5)
            
            metrics['retrained'] = True
            metrics['new_attack_success_rate'] = new_attack_success_rate
            metrics['improvement'] = attack_success_rate - new_attack_success_rate
        else:
            metrics['retrained'] = False
        
        return metrics
    
    def run_multiple_iterations(self, n_iterations: int = 5):
        """Run multiple iterations and show improvement"""
        print(f"Running {n_iterations} iterations of closed loop...\n")
        
        for i in range(n_iterations):
            metrics = self.run_iteration()
            print(f"Iteration {metrics['iteration']}:")
            print(f"  Attack Success Rate: {metrics['attack_success_rate']:.2%}")
            print(f"  Detection F1: {metrics['detection_f1']:.2f}")
            print(f"  Detection ROC-AUC: {metrics['detection_roc_auc']:.2f}")
            if metrics.get('retrained'):
                print(f"  ✓ Retrained - Attack Success: {metrics['attack_success_rate']:.2%} → {metrics['new_attack_success_rate']:.2%} (Improvement: {metrics['improvement']:.2%})")
            print()
        
        # Show overall improvement
        initial_attack_success = self.history['attack_success_rate']
        final_attack_success = self.history[-1]['attack_success_rate']
        initial_f1 = self.history['detection_f1']
        final_f1 = self.history[-1]['detection_f1']
        
        print("=" * 60)
        print("CLOSED-LOOP IMPROVEMENT SUMMARY")
        print("=" * 60)
        print(f"Attack Success Rate: {initial_attack_success:.2%} → {final_attack_success:.2%} ({(initial_attack_success - final_attack_success)*100:.1f}% reduction)")
        print(f"Detection F1 Score: {initial_f1:.2f} → {final_f1:.2f} (+{(final_f1 - initial_f1):.2f})")
        print(f"Detection ROC-AUC: {self.history['detection_roc_auc']:.2f} → {self.history[-1]['detection_roc_auc']:.2f}")
```

---

### FRONTEND (Streamlit Dashboard)

**Purpose**: Demo UI for judges to interact with the system
**Implementation**:

```python
import streamlit as st
import plotly.express as px

st.set_page_config(page_title="FraudForge", page_icon="🔒", layout="wide")

# Mastercard colors
st.markdown("""
<style>
    .main {
        background-color: #FFFFFF;
    }
    h1 {
        color: #EB001B;
    }
    h2 {
        color: #000000;
    }
    .metric-card {
        background-color: #f0f0f0;
        padding: 20px;
        border-radius: 10px;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

st.title("🔒 FraudForge: Red Team/Blue Team AI for Payment Fraud")
st.markdown("**Mastercard Innovation Challenge 2026** | **Closed-Loop Adversarial AI**")

# Sidebar: Navigation
option = st.sidebar.selectbox(
    "Select View",
    ["🏠 Home", "🔍 Attack Discovery", "⚔️ Attack Generation", "🛡️ Fraud Detection", "🔄 Closed-Loop Evaluation"]
)

if option == "🏠 Home":
    st.header("Welcome to FraudForge")
    st.markdown("""
    ### Three Pillars:
    1. **IDENTIFY** - Research and generate emerging GenAI-powered payment fraud attacks
    2. **GENERATE** - Create high-fidelity synthetic fraud transactions
    3. **DEFEND** - Detect generated attacks accurately while keeping false positives low
    
    ### Key Features:
    - **5 Attack Vectors**: AI Phishing→ATO, Synthetic Identity, Voice Cloning→UPI, AI Agent→Intent Mismatch, Adversarial Transactions
    - **Incremental Intelligence**: V0 (Transaction) → V1 (Behavioral) → V4 (Intent) → V5 (Agent)
    - **Closed-Loop**: Attack → Detect → Learn → Improve → Re-Attack
    - **Adversarial Training**: RL-based optimization improves robustness
    
    ### Expected Performance:
    | Intelligence Layer | Detection F1 | Attack Success Rate |
    |-------------------|:------------:|:-------------------:|
    | V0 (Baseline) | 0.82-0.85 | 35-40% |
    | V1 (Behavioral) | 0.87-0.90 | 20-25% |
    | V4 (Intent) | 0.90-0.93 | 10-15% |
    | V5 (Agent) | 0.93-0.95 | 5-10% |
    """)

elif option == "🔍 Attack Discovery":
    st.header("🔍 Attack Discovery (Red Team)")
    
    # Input: Threat intelligence
    threat_intel = st.text_area(
        "Enter Threat Intelligence",
        value="""Recent reports show:
1. AI phishing scams targeting bank customers (Feb 2026)
2. Deepfake voice scams impersonating family members (Jan 2026)
3. Synthetic identity fraud up 2137% since 2022
4. Mastercard Agent Pay launched with 35+ partners (June 2026)
5. UPI frauds peak at 12.64 lakh cases in FY25 (₹981 crore losses)""",
        height=150
    )
    
    if st.button("Generate Attack Hypotheses"):
        with st.spinner("Researching..."):
            hypotheses = fraud_research_agent.generate_hypotheses(threat_intel)
        
        st.success(f"Generated {len(hypotheses)} attack hypotheses")
        
        # Display hypotheses
        for i, hyp in enumerate(hypotheses):
            with st.expander(f"Attack {i+1}: {hyp['attack_name']}"):
                st.write(f"**Attack Surface**: {hyp['attack_surface']}")
                st.write(f"**AI Component**: {hyp['ai_component']}")
                st.write(f"**Payment Impact**: {hyp['payment_impact']}")
                st.write(f"**Detectable Signals**: {', '.join(hyp['detectable_signals'])}")
                st.write(f"**OWASP Mapping**: {', '.join(hyp['owasp_mapping'])}")
                st.write(f"**Confidence Score**: {hyp['confidence_score']:.2f}")

elif option == "⚔️ Attack Generation":
    st.header("⚔️ Attack Generation (Red Team)")
    
    attack_type = st.selectbox(
        "Select Attack Type",
        ["AI_Phishing_ATO", "Synthetic_Identity", "Voice_Cloning_UPI", "AI_Agent_Intent_Mismatch", "Adversarial_Transaction"]
    )
    
    if st.button("Generate Synthetic Fraud"):
        with st.spinner("Generating..."):
            synthetic_fraud = attack_generator.generate_synthetic_fraud(n_samples=2000, attack_type=attack_type)
        
        st.success(f"Generated {len(synthetic_fraud)} synthetic fraud transactions")
        
        # Show distribution comparison
        fig = px.histogram(
            pd.DataFrame({
                'Real Fraud': fraud_samples['TransactionAmt'],
                f'Synthetic ({attack_type})': synthetic_fraud['TransactionAmt']
            }),
            barmode='overlay',
            title="Real vs Synthetic Fraud Distribution"
        )
        st.plotly_chart(fig)
        
        # Show fidelity metrics
        fidelity = attack_generator.evaluate_fidelity(synthetic_fraud, fraud_samples)
        st.metric("Attack Fidelity Score (AFS)", f"{fidelity['attack_fidelity_score']:.1f}")
        st.write(f"**KS Test (TransactionAmt)**: {fidelity['ks_tests']['TransactionAmt']['ks_statistic']:.3f} (target: <0.1)")

elif option == "🛡️ Fraud Detection":
    st.header("🛡️ Fraud Detection (Blue Team)")
    
    intelligence_layer = st.selectbox(
        "Select Intelligence Layer",
        ["V0 (Transaction)", "V1 (Behavioral)", "V4 (Intent)", "V5 (Agent)"]
    )
    
    # Upload transaction
    uploaded_file = st.file_uploader("Upload Transaction CSV", type=['csv'])
    
    if uploaded_file:
        transaction = pd.read_csv(uploaded_file)
        
        if st.button("Detect Fraud"):
            with st.spinner("Scoring..."):
                # Select appropriate detector
                if intelligence_layer == "V0 (Transaction)":
                    detector = detector_v0
                elif intelligence_layer == "V1 (Behavioral)":
                    detector = detector_v1
                elif intelligence_layer == "V4 (Intent)":
                    detector = detector_v4
                elif intelligence_layer == "V5 (Agent)":
                    detector = detector_v5
                
                fraud_prob = detector.predict(transaction)
                risk_score = fraud_prob * 100
            
            st.metric("Fraud Probability", f"{fraud_prob:.2%}")
            st.metric("Risk Score", f"{risk_score:.0f}/100")
            
            if fraud_prob > 0.8:
                st.error("🚨 FRAUD DETECTED - HIGH CONFIDENCE")
                st.info("**Mitigation**: Block transaction immediately, notify user and issuer")
            elif fraud_prob > 0.5:
                st.warning("⚠️ SUSPICIOUS TRANSACTION - MEDIUM CONFIDENCE")
                st.info("**Mitigation**: Step-up authentication (OTP/Biometric), manual review")
            else:
                st.success("✅ Transaction Approved")
            
            # Show explanation
            explanation = detector.explain(transaction, top_k=5)
            st.subheader("Top 5 Features (SHAP)")
            st.dataframe(explanation)

elif option == "🔄 Closed-Loop Evaluation":
    st.header("🔄 Closed-Loop Evaluation (Orchestrator)")
    
    n_iterations = st.slider("Number of Iterations", min_value=1, max_value=10, value=5)
    
    if st.button("Run Closed-Loop"):
        with st.spinner("Running closed loop..."):
            orchestrator = ClosedLoopOrchestrator(red_team, blue_team)
            history = orchestrator.run_multiple_iterations(n_iterations)
        
        # Show improvement chart
        fig = px.line(
            x=[h['iteration'] for h in orchestrator.history],
            y=[h['attack_success_rate'] for h in orchestrator.history],
            title="Attack Success Rate Over Iterations (Lower is Better)",
            labels={'x': 'Iteration', 'y': 'Attack Success Rate'}
        )
        st.plotly_chart(fig)
        
        # Show metrics table
        st.subheader("Performance Metrics")
        metrics_df = pd.DataFrame(orchestrator.history)
        st.dataframe(metrics_df)
        
        # Show summary
        initial_attack_success = orchestrator.history['attack_success_rate']
        final_attack_success = orchestrator.history[-1]['attack_success_rate']
        initial_f1 = orchestrator.history['detection_f1']
        final_f1 = orchestrator.history[-1]['detection_f1']
        
        st.success(f"""
        ### Closed-Loop Improvement Summary
        - **Attack Success Rate**: {initial_attack_success:.2%} → {final_attack_success:.2%} ({(initial_attack_success - final_attack_success)*100:.1f}% reduction)
        - **Detection F1 Score**: {initial_f1:.2f} → {final_f1:.2f} (+{(final_f1 - initial_f1):.2f})
        - **Detection ROC-AUC**: {orchestrator.history['detection_roc_auc']:.2f} → {orchestrator.history[-1]['detection_roc_auc']:.2f}
        """)
```

---

## REPOSITORY STRUCTURE
