const BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`${res.status} ${path}: ${await res.text()}`);
  }
  return res.json() as Promise<T>;
}

export type Metrics = {
  precision: number;
  recall: number;
  f1: number;
  pr_auc: number;
  roc_auc?: number;
  fpr: number;
  threshold?: number;
};

export type DashboardSummary = {
  transactions_simulated: number;
  attack_runs: number;
  detection_rate: number;
  holdout_detection_rate: number;
  precision: number;
  recall: number;
  f1: number;
  pr_auc: number;
  false_positive_rate: number;
  attack_success_rate: number | null;
  attack_fidelity: number | null;
  model_version: string;
  backend?: string;
  latest_simulation: string | null;
  n_features: number;
};

export type RunSummary = {
  simulation_id: string;
  attack_id: string;
  attack_name: string;
  variant_id: string;
  difficulty: string;
  scale: number;
  detection_rate: number;
  attack_success: number;
  precision: number;
  recall: number;
  f1: number;
  pr_auc: number;
  fpr: number;
  fidelity: number;
  model_version: string;
  novelty: string;
  status?: string;
};

export type ThreatCard = ThreatSummary & {
  evidence?: string;
  evidence_level?: string;
  objective?: string;
  variant_count?: number;
  supported_difficulties?: string[];
  simulation_ready?: boolean;
  status?: string;
};

export type ThreatDetail = {
  attack_id: string;
  name: string;
  category: string;
  evidence: string;
  objective: string;
  variants: number;
  variant_list: { id: string; name: string }[];
  supported_difficulties: string[];
  detection_signals: string[];
  simulation_template: string;
  family: string;
  simulation_ready: boolean;
  expected_mitigation?: string;
};

export type BlueModel = {
  model_version: string;
  algorithm: string;
  backend?: string;
  training_dataset: string;
  features: number;
  feature_names: string[];
  last_trained: string | null;
  thresholds: { allow: number; step_up: number; review: number; detect: number };
  holdout: Partial<Metrics>;
};

export type RiskLane = {
  enabled: boolean;
  phase: string;
  source: string | null;
};

export type Confusion = {
  tn: number;
  fp: number;
  fn: number;
  tp: number;
  threshold: number;
  source?: string;
};

export type ThresholdPoint = Metrics & { n?: number; n_pos?: number };

export type TxRow = {
  transaction_id: string;
  simulation_id?: string;
  amount?: number;
  fraud_probability: number;
  decision: string;
  attack_id?: string;
  attack_family?: string;
  merchant_id?: string;
  device_id?: string;
  customer_id?: string;
  beneficiary_id?: string;
  hour_of_day?: number;
};

export type TxExplanation = {
  transaction_id: string;
  fraud_probability: number;
  decision: string;
  explanation: Explanation[];
  gap?: string;
};

export type ModelMetrics = {
  logreg?: Metrics;
  lightgbm?: Metrics;
  backend?: string;
  per_attack?: Record<string, Metrics>;
  fidelity?: Record<string, number>;
  model_version?: string;
};

export type Explanation = {
  feature: string;
  shap_value: number;
  value: number;
};

export type ScoredRow = {
  transaction_id: string;
  amount?: number;
  fraud_probability: number;
  decision: string;
  attack_family?: string;
  missed?: boolean;
  explanation?: Explanation[];
};

export type Narrative = {
  finding: string;
  detected: string[];
  weak: string[];
  red: string;
  blue: string;
};

export type Simulation = {
  simulation_id: string;
  attack_family: string;
  generated: number;
  detected?: number;
  missed: number;
  detection_rate: number;
  metrics: Metrics;
  narrative?: Narrative;
  report: string;
  missed_transactions: ScoredRow[];
  preview: ScoredRow[];
};

export type GraphNode = {
  id: string;
  type: string;
  label: string;
  degree?: number;
  role?: string;
  flag?: string;
  detected?: boolean | null;
};

export type GraphEdge = {
  source: string;
  target: string;
  relation: string;
  label?: string;
  src_type?: string;
  dst_type?: string;
};

export type GraphHub = {
  type: string;
  id: string;
  customers: number;
};

export type GraphPathStep = {
  id: string;
  label: string;
  type: string;
  present?: boolean;
  status?: string;
};

export type GraphPayload = {
  nodes: GraphNode[];
  edges: GraphEdge[];
  n_edges?: number;
  n_nodes?: number;
  shared_hubs?: GraphHub[];
  attack_networks?: number;
  edge_fingerprint?: string[];
  edge_table?: Record<string, unknown>[];
  family?: string;
  attack_id?: string;
  variant_id?: string;
  stats?: {
    n_nodes?: number;
    n_edges?: number;
    shared_hubs?: number;
    compromised_accounts?: number;
    new_devices?: number;
    new_beneficiaries?: number;
    new_ips?: number;
  };
  focus?: { nodes: GraphNode[]; edges: GraphEdge[]; n_nodes?: number; n_edges?: number };
  path?: GraphPathStep[];
  blue?: { label: string; status: string }[];
  motif?: { id: string; label: string; present: boolean }[];
  agent_events?: {
    transaction_id: string;
    agent_id: string;
    tool: string;
    intent: string;
    in_scope: boolean;
    reason: string;
  }[];
};

export type RedTeamResult = Simulation & {
  attack_id?: string;
  attack_name?: string;
  variant_id?: string;
  difficulty?: string;
  fidelity?: Record<string, number>;
  entities?: {
    entities?: number;
    customers?: number;
    devices?: number;
    ips?: number;
    beneficiaries?: number;
    attack_networks?: number;
  };
  context?: {
    shared_devices?: number;
    shared_ips?: number;
    mule_networks?: number;
  };
  finding?: string;
  detection_signals?: string[];
  contract?: Record<string, unknown>;
  graph?: GraphPayload;
  agent_events?: GraphPayload["agent_events"];
  agent_event_count?: number;
};

export type ThreatSummary = {
  attack_id: string;
  name: string;
  category: string;
  family: string;
  variants: { id: string; name: string }[];
  detection_signals: string[];
};

export type LeaderboardRow = {
  attack_id: string;
  name: string;
  difficulty: string;
  detection_rate: number | null;
  attack_success: number | null;
  evasion: number | null;
  pr_auc: number | null;
  fidelity: number | null;
  scale: number;
  novelty: string;
  model_version: string | null;
};

export type RegressionRow = {
  simulation_id: string;
  attack_id: string;
  attack_name: string;
  variant_id: string;
  difficulty: string;
  seed: number;
  scale: number;
  model_version: string;
  detection_rate: number;
  attack_success: number;
  precision: number;
  recall: number;
  f1: number;
  pr_auc: number;
  fpr: number;
  fidelity: number;
  novelty: string;
};

export type BlueTeamLab = {
  model_version: string;
  backend?: string;
  holdout: Partial<Metrics>;
  logreg?: Partial<Metrics>;
  per_attack?: Record<string, Metrics>;
  features: { feature: string; importance: number }[];
  weaknesses: RegressionRow[];
  history: RegressionRow[];
  leaderboard: LeaderboardRow[];
};

export type DefenseCoverage = {
  attack_id: string;
  name: string;
  tested: number;
  blocked: number;
  missed: number;
  recall: number;
  difficulty?: string | null;
  model_version?: string | null;
  current_detector?: boolean;
};

export type DefenseCenter = {
  model_version: string;
  backend?: string;
  source: string;
  tested: number;
  blocked: number;
  bypassed: number;
  detection_rate: number;
  precision: number;
  recall: number;
  f1: number;
  pr_auc: number;
  false_positive_rate: number;
  coverage: DefenseCoverage[];
  weakest?: DefenseCoverage | null;
  latest_run?: RunSummary | null;
  run_count: number;
};

export type LoopRound = {
  simulation_id?: string;
  attack_id?: string;
  attack_name?: string;
  variant_id?: string;
  difficulty?: string;
  seed?: number;
  scale?: number;
  generated?: number;
  detected?: number;
  missed?: number;
  detection_rate?: number;
  attack_success?: number;
  precision?: number;
  recall?: number;
  f1?: number;
  model_version?: string;
  finding?: string;
};

export type LoopSummary = {
  round: number;
  source?: string;
  blue_model: string;
  current?: LoopRound | RunSummary | null;
  prior?: LoopRound | RunSummary | null;
  before?: LoopRound | null;
  after?: LoopRound | null;
  delta?: {
    detection_rate?: number;
    attack_success?: number;
    detected?: number;
    missed?: number;
  };
  contract?: {
    attack_id?: string;
    variant_id?: string;
    variant_name?: string;
    family?: string;
    difficulty?: string;
    seed?: number;
    transaction_count?: number;
  };
  holdout?: Partial<Metrics>;
  weakest?: LoopRound | RunSummary | null;
  note?: string;
};

export type BlueDashboard = {
  data_available: boolean;
  reason?: string;
  transactions?: number;
  threats?: number;
  detection_rate?: number;
  precision?: number;
  recall?: number;
  f1?: number;
  pr_auc?: number;
  fpr?: number;
  active_high_risk?: number;
  coverage?: Record<string, number>;
  model_id?: string;
  clusters?: Record<string, number>;
};

export type BlueDetection = {
  transaction_id: string;
  clock?: string;
  attack_prediction?: string;
  risk_score?: number;
  classification_confidence?: number;
  action?: string;
  fraud_probability?: number;
  amount?: number;
  customer_id?: string;
  beneficiary_id?: string;
};

export type BlueSignal = { signal: string; fired: boolean; severity: string };

export type BlueDetectionDetail = {
  transaction_id: string;
  clock?: string;
  risk_score?: number;
  fraud_probability?: number;
  attack_classification?: string;
  classification_confidence?: number;
  signals?: BlueSignal[];
  action?: string;
  reason?: string;
  customer_id?: string;
  beneficiary_id?: string;
  device_id?: string;
  ip_id?: string;
  amount?: number;
};

export type NetworkNode = { id: string; type: string };
export type NetworkEdge = { source: string; relation: string; target: string };

export type BlueNetwork = {
  data_available: boolean;
  reason?: string;
  high_risk_clusters?: number;
  shared_devices?: number;
  shared_ips?: number;
  suspicious_beneficiaries?: number;
  mule_networks?: number;
  focus?: { entity_id: string; nodes: NetworkNode[]; edges: NetworkEdge[] };
  profile?: {
    entity_id?: string;
    found?: boolean;
    connected_customers?: number;
    transactions?: number;
    total_value?: number;
    devices?: number;
    ips?: number;
    fan_in?: number;
    first_seen?: number | null;
    risk_score?: number;
    classification?: string;
    confidence?: number;
    signals?: BlueSignal[];
  };
};

export type BlueCoverage = {
  data_available: boolean;
  reason?: string;
  attacks_detected?: number;
  distribution?: Record<string, number>;
  recall_by_family?: Record<string, number>;
  matrix?: { family: string; generated: number; detected: number; missed: number; recall?: number }[];
};

export type BlueEntity = {
  found: boolean;
  reason?: string;
  entity_type?: string;
  entity_id?: string;
  connected_accounts?: number;
  devices?: number;
  ips?: number;
  transactions?: number;
  total_value?: number;
};

export type BlueTimelineEvent = {
  timestamp: number;
  transaction_id?: string;
  customer_id?: string;
  beneficiary_id?: string;
  amount?: number;
};

export type BlueMitigation = {
  counts: Record<string, number>;
  items: {
    transaction_id: string;
    risk_score: number;
    attack?: string;
    recommended?: string;
    band?: string;
    beneficiary_id?: string;
    customer_id?: string;
  }[];
  cluster?: {
    beneficiary_id: string;
    accounts: number;
    devices: number;
    ips: number;
    recommended?: string;
  } | null;
};

export type BlueReport = {
  data_available: boolean;
  reason?: string;
  simulation_id?: string;
  report?: string;
  payload?: Record<string, unknown>;
};

export type BlueCompare = {
  data_available: boolean;
  reason?: string;
  baseline?: string;
  candidate?: string;
  holdout?: { p0?: Metrics; p2?: Metrics };
  coordinated_attacks?: Record<string, { p0_recall: number; p2_recall: number }>;
  per_attack?: Record<string, Metrics & { attack_recall?: number }>;
};
