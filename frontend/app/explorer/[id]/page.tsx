"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, type TxExplanation } from "@/lib/api";
import { inr, label, pct } from "@/lib/format";
import { PageTitle, Section } from "@/components/ui";

type Tx = Record<string, unknown>;
type Feat = { feature: string; value: unknown };

export default function TransactionDetail() {
  const { id } = useParams<{ id: string }>();
  const [tx, setTx] = useState<Tx | null>(null);
  const [features, setFeatures] = useState<Feat[]>([]);
  const [expl, setExpl] = useState<TxExplanation | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!id) return;
    const encoded = encodeURIComponent(id);
    Promise.all([
      api<Tx>(`/transactions/${encoded}`),
      api<{ features: Feat[] }>(`/transactions/${encoded}/features`),
      api<TxExplanation>(`/transactions/${encoded}/explanation`),
    ])
      .then(([t, f, e]) => {
        setTx(t);
        setFeatures(f.features || []);
        setExpl(e);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Not found"));
  }, [id]);

  const amount = typeof tx?.amount === "number" ? tx.amount : Number(tx?.amount);
  const risk = typeof tx?.fraud_probability === "number" ? tx.fraud_probability : Number(tx?.fraud_probability);

  return (
    <div className="rise space-y-10">
      <PageTitle title={String(tx?.transaction_id || id)}>
        Investigation of a scored payment. Network and geo scores are P2 graph features, not a GNN.
      </PageTitle>
      {error ? <p className="font-mono text-sm text-signal">{error}</p> : null}

      <Section title="Transaction">
        <dl className="mt-4 grid grid-cols-2 gap-x-8 gap-y-4 sm:grid-cols-4 text-sm">
          {[
            ["Amount", inr(amount)],
            ["Merchant", String(tx?.merchant_id || "—")],
            ["Beneficiary", String(tx?.beneficiary_id || "—")],
            ["Device", String(tx?.device_id || "—")],
            ["Customer", String(tx?.customer_id || "—")],
            ["Fraud probability", pct(risk)],
            ["Decision", String(tx?.decision || "—")],
            ["Attack", String(tx?.attack_id || tx?.attack_family || "—")],
          ].map(([k, v]) => (
            <div key={k} className="border-t border-white/10 pt-3">
              <dt className="text-xs text-white/45">{k}</dt>
              <dd className="mt-1 font-mono">{v}</dd>
            </div>
          ))}
        </dl>
      </Section>

      <Section title="Customer behavior">
        <dl className="mt-4 grid grid-cols-2 gap-4 text-sm sm:grid-cols-3">
          {features
            .filter((f) =>
              ["transaction_count_1h", "transaction_count_24h", "avg_amount_30d", "amount_deviation", "account_age_days"].includes(
                f.feature,
              ),
            )
            .map((f) => (
              <div key={f.feature} className="border-t border-white/10 pt-3">
                <dt className="text-xs text-white/45">{label(f.feature)}</dt>
                <dd className="mt-1 font-mono">{String(f.value ?? "—")}</dd>
              </div>
            ))}
        </dl>
      </Section>

      <Section title="Device">
        <p className="mt-4 font-mono text-sm">
          {String(tx?.device_id || "—")} · age {String(tx?.device_age_days ?? "—")} days
        </p>
      </Section>

      <Section title="Geo">
        <dl className="mt-4 grid grid-cols-2 gap-4 text-sm">
          {[
            ["distance_from_home", tx?.distance_from_home],
            ["geo_velocity", tx?.geo_velocity],
            ["geo_risk", tx?.geo_risk],
          ].map(([k, v]) => (
            <div key={String(k)} className="border-t border-white/10 pt-3">
              <dt className="text-xs text-white/45">{label(String(k))}</dt>
              <dd className="mt-1 font-mono">{v == null ? "—" : String(v)}</dd>
            </div>
          ))}
        </dl>
      </Section>

      <Section title="Network">
        <dl className="mt-4 grid grid-cols-2 gap-4 text-sm">
          {[
            ["network_risk", tx?.network_risk],
            ["beneficiary_fan_in", tx?.beneficiary_fan_in],
            ["shared_device_score", tx?.shared_device_score],
            ["shared_ip_score", tx?.shared_ip_score],
          ].map(([k, v]) => (
            <div key={String(k)} className="border-t border-white/10 pt-3">
              <dt className="text-xs text-white/45">{label(String(k))}</dt>
              <dd className="mt-1 font-mono">{v == null ? "—" : String(v)}</dd>
            </div>
          ))}
        </dl>
      </Section>

      <Section title="Intent">
        <p className="mt-4 font-mono text-xs text-white/35">Coming in P3</p>
      </Section>

      <Section title="Agent">
        <p className="mt-4 font-mono text-xs text-white/35">Coming in P3</p>
      </Section>

      <Section title="ML explanation">
        {expl ? (
          <div className="mt-4 grid gap-8 lg:grid-cols-[1fr_minmax(0,280px)]">
            <div>
              <p className="text-sm text-white/60">{expl.gap}</p>
              <ul className="mt-4">
                {(expl.explanation || []).map((row) => (
                  <li key={row.feature} className="flex justify-between border-t border-white/10 py-2 text-sm">
                    <span>{label(row.feature)}</span>
                    <span className="font-mono text-white/50">
                      {row.value} · shap {row.shap_value.toFixed(3)}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
            <div className="h-48">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={(expl.explanation || []).map((e) => ({ feature: e.feature, shap: e.shap_value }))}
                  layout="vertical"
                >
                  <XAxis type="number" hide />
                  <YAxis type="category" dataKey="feature" width={110} tick={{ fill: "#8a8a8a", fontSize: 11 }} />
                  <Tooltip contentStyle={{ background: "#0A0A0A", border: "1px solid #222" }} />
                  <Bar dataKey="shap" fill="#FF5F00" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        ) : (
          <p className="mt-4 text-sm text-white/40">No explanation for this row.</p>
        )}
      </Section>
    </div>
  );
}
