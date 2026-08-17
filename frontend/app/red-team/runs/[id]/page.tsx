"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { AttackGraph } from "@/components/attack-graph";
import { ReportPane } from "@/components/report";
import { api, type GraphPayload, type RedTeamResult, type ScoredRow } from "@/lib/api";
import { num, pct } from "@/lib/format";
import { Kpi, PageTitle, Section } from "@/components/ui";

type Metrics = {
  generated: number;
  detected: number;
  missed: number;
  detection_rate: number;
  attack_success_rate: number;
  precision: number;
  recall: number;
  f1: number;
  pr_auc: number;
  fpr: number;
  fidelity: number;
  fidelity_breakdown?: Record<string, number> | null;
  attack_name: string;
  variant_id: string;
  difficulty: string;
  attack_id: string;
};

type Timeline = { stages: { id: string; label: string; done: boolean; detail?: string }[] };
type Signals = { detected: string[]; weak: string[]; note?: string };

export default function RunDetail() {
  const { id } = useParams<{ id: string }>();
  const [run, setRun] = useState<RedTeamResult | null>(null);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [signals, setSignals] = useState<Signals | null>(null);
  const [timeline, setTimeline] = useState<Timeline | null>(null);
  const [misses, setMisses] = useState<ScoredRow[]>([]);
  const [graph, setGraph] = useState<GraphPayload | null>(null);
  const [tab, setTab] = useState<"overview" | "missed" | "graph" | "report">("overview");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!id) return;
    Promise.all([
      api<RedTeamResult>(`/red-team/runs/${id}`),
      api<Metrics>(`/red-team/runs/${id}/metrics`),
      api<Signals>(`/red-team/runs/${id}/signals`),
      api<Timeline>(`/red-team/runs/${id}/timeline`),
      api<{ misses: ScoredRow[] }>(`/red-team/runs/${id}/misses`),
    ])
      .then(([r, m, s, t, miss]) => {
        setRun(r);
        setMetrics(m);
        setSignals(s);
        setTimeline(t);
        setMisses(miss.misses || []);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Run not found"));
  }, [id]);

  async function replay() {
    if (!id) return;
    setBusy(true);
    try {
      const body = await api<RedTeamResult>(`/red-team/runs/${id}/replay`, { method: "POST" });
      setRun(body);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Replay failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rise space-y-10">
      <PageTitle title={metrics?.attack_name || id}>
        {metrics?.attack_id} · {metrics?.difficulty} · {num(metrics?.generated)} transactions
      </PageTitle>
      {error ? <p className="font-mono text-sm text-signal">{error}</p> : null}

      <div className="flex flex-wrap gap-6 font-mono text-[11px] uppercase tracking-[0.18em] text-white/35">
        {(["overview", "missed", "graph", "report"] as const).map((t) => (
          <button
            key={t}
            type="button"
            className={tab === t ? "text-signal" : "hover:text-white"}
            onClick={() => {
              setTab(t);
              if (t === "graph" && id && !graph) {
                void api<GraphPayload>(`/red-team/runs/${id}/graph`).then(setGraph).catch(() => undefined);
              }
            }}
          >
            {t}
          </button>
        ))}
        <button type="button" disabled={busy} className="hover:text-white" onClick={() => void replay()}>
          {busy ? "Replaying…" : "Replay"}
        </button>
      </div>

      {tab === "overview" ? (
        <>
          <dl className="grid grid-cols-2 gap-x-8 gap-y-6 sm:grid-cols-5">
            <Kpi label="Generated" value={num(metrics?.generated)} />
            <Kpi label="Detected" value={num(metrics?.detected)} />
            <Kpi label="Missed" value={num(metrics?.missed)} />
            <Kpi label="Detection" value={pct(metrics?.detection_rate)} />
            <Kpi label="Precision" value={pct(metrics?.precision)} />
            <Kpi label="Recall" value={pct(metrics?.recall)} />
            <Kpi label="F1" value={pct(metrics?.f1)} />
            <Kpi label="PR-AUC" value={pct(metrics?.pr_auc)} hint="mix-set, high prevalence" />
            <Kpi label="FPR" value={pct(metrics?.fpr)} />
            <Kpi label="Fidelity" value={pct(metrics?.fidelity)} />
          </dl>
          {metrics?.fidelity_breakdown && typeof metrics.fidelity_breakdown === "object" ? (
            <Section title="Attack fidelity">
              <dl className="mt-4 grid grid-cols-2 gap-x-8 gap-y-4 sm:grid-cols-4">
                {(
                  [
                    ["amount_distribution", "Amount"],
                    ["time_distribution", "Temporal"],
                    ["velocity_distribution", "Velocity"],
                    ["merchant_distribution", "Merchant"],
                    ["customer_behavior", "Customer"],
                    ["sequence_similarity", "Sequence"],
                    ["beneficiary_behavior", "Beneficiary"],
                    ["overall_fidelity", "Overall"],
                  ] as const
                ).map(([key, label]) => {
                  const value = metrics.fidelity_breakdown?.[key];
                  return value == null ? null : <Kpi key={key} label={label} value={pct(Number(value))} />;
                })}
              </dl>
            </Section>
          ) : null}
          <Section title="Attack lifecycle">
            <ol className="mt-4 max-w-md">
              {(timeline?.stages || []).map((stage, i) => (
                <li key={stage.id} className="border-t border-white/10 py-3 text-sm">
                  <span className="font-mono text-[11px] text-white/35">{String(i + 1).padStart(2, "0")}</span>
                  <span className="ml-3">{stage.label}</span>
                  {stage.detail ? <span className="ml-3 font-mono text-[11px] text-white/40">{stage.detail}</span> : null}
                </li>
              ))}
            </ol>
          </Section>
          <div className="grid gap-12 lg:grid-cols-2">
            <Section title="Detected signals">
              <ul className="mt-4">
                {(signals?.detected || []).map((s) => (
                  <li key={s} className="border-t border-white/10 py-2.5 text-sm">
                    {s}
                  </li>
                ))}
              </ul>
            </Section>
            <Section title="Weak / missing signals">
              <p className="mt-4 text-sm text-white/50">
                {(signals?.weak || []).join(", ") || "No strong additional signals identified."}
              </p>
              {signals?.note ? <p className="mt-3 text-xs text-white/35">{signals.note}</p> : null}
            </Section>
          </div>
        </>
      ) : null}

      {tab === "missed" ? (
        <table className="w-full text-left text-sm">
          <thead className="font-mono text-[11px] uppercase tracking-[0.16em] text-white/35">
            <tr>
              <th className="pb-3 font-normal">Transaction</th>
              <th className="pb-3 font-normal">Attack</th>
              <th className="pb-3 font-normal">Risk</th>
              <th className="pb-3 font-normal">Actual</th>
              <th className="pb-3 font-normal">Decision</th>
            </tr>
          </thead>
          <tbody>
            {misses.map((row) => (
              <tr key={row.transaction_id} className="border-t border-white/10">
                <td className="py-3 font-mono text-xs">
                  <Link href={`/explorer/${encodeURIComponent(row.transaction_id)}`} className="hover:text-signal">
                    {row.transaction_id}
                  </Link>
                </td>
                <td className="py-3 font-mono text-xs">{metrics?.attack_id}</td>
                <td className="py-3 font-mono">{(row.fraud_probability * 100).toFixed(1)}%</td>
                <td className="py-3">Fraud</td>
                <td className="py-3">{row.decision}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}

      {tab === "graph" ? (
        graph ? (
          <AttackGraph
            graph={graph}
            events={run?.agent_events}
            title={metrics?.attack_name || run?.attack_name}
            subtitle={`${metrics?.attack_id || ""} · ${metrics?.variant_id || ""} · ${metrics?.difficulty || ""}`}
          />
        ) : (
          <p className="text-sm text-white/40">Loading graph…</p>
        )
      ) : null}

      {tab === "report" && run ? <ReportPane result={run} /> : null}
    </div>
  );
}
