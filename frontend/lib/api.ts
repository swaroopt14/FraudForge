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
};

export type ModelMetrics = {
  logreg?: Metrics;
  lightgbm?: Metrics;
  backend?: string;
  per_attack?: Record<string, Metrics>;
  fidelity?: Record<string, number>;
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
  variant_id?: string;
  model_id?: string;
};

export type AttackCatalogItem = {
  id: string;
  name: string;
  tier?: string;
  mutates?: string[];
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

export type BlueSignal = {
  signal: string;
  fired: boolean;
  severity: string;
};

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

