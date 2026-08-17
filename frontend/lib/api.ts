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
};
