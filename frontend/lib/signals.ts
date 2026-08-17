export const SIGNAL_BEHAVIOR: Record<string, { normal: string; attack: string }> = {
  beneficiary_is_new: { normal: "Known beneficiary", attack: "New beneficiary" },
  destination_concentration: { normal: "Normal destination mix", attack: "Concentrated destination" },
  device_age_days: { normal: "Established device", attack: "New or swapped device" },
  distance_from_home: { normal: "Usual geography", attack: "Far from home" },
  transaction_count_1h: { normal: "Normal velocity", attack: "Burst velocity" },
  transaction_count_24h: { normal: "Normal daily volume", attack: "Elevated 24h volume" },
  failed_auth_count: { normal: "Clean auth", attack: "Failed authentications" },
  merchant_risk: { normal: "Typical merchant", attack: "Higher-risk merchant" },
  amount_deviation: { normal: "Usual amount", attack: "Amount outlier" },
  merchant_count_24h: { normal: "Few merchants", attack: "Merchant hopping" },
};

export function behaviorRows(signals: string[] | undefined) {
  return (signals || []).map((id) => ({
    id,
    ...(SIGNAL_BEHAVIOR[id] || { normal: "Typical pattern", attack: id.replaceAll("_", " ") }),
  }));
}
