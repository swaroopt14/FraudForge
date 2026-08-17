export function pct(n?: number | null) {
  if (n == null || Number.isNaN(n)) return "—";
  return `${(n * 100).toFixed(1)}%`;
}

export function num(n?: number | null) {
  if (n == null || Number.isNaN(n)) return "—";
  return n.toLocaleString("en-IN");
}

export function inr(n?: number | null) {
  if (n == null || Number.isNaN(n)) return "—";
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(n);
}

export const FAMILY_SHORT: Record<string, string> = {
  account_takeover: "ATO",
  beneficiary_anomaly: "BEN",
  velocity_attack: "VEL",
  mule_network: "MUL",
  amount_anomaly: "AMT",
  shared_device: "DEV",
  shared_ip: "IP",
  geo_anomaly: "GEO",
  low_and_slow: "LOW",
  combined_context: "CTX",
};

export function familyLabel(id?: string | null) {
  if (!id) return "—";
  return id.replaceAll("_", " ");
}

export function familyShort(id?: string | null) {
  if (!id) return "—";
  return FAMILY_SHORT[id] || id.slice(0, 3).toUpperCase();
}
