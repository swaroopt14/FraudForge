"use client";

import { useEffect, useState } from "react";
import { api, type ModelMetrics } from "@/lib/api";

function pct(n?: number) {
  if (n == null || Number.isNaN(n)) return "—";
  return `${(n * 100).toFixed(1)}%`;
}

export default function CommandCenter() {
  const [health, setHealth] = useState("checking");
  const [metrics, setMetrics] = useState<ModelMetrics | null>(null);
  const [importance, setImportance] = useState<{ feature: string; importance: number }[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const h = await api<{ status: string }>("/health");
        const m = await api<ModelMetrics>("/model/metrics");
        const f = await api<{ features: { feature: string; importance: number }[] }>("/model/feature-importance");
        if (cancelled) return;
        setHealth(h.status);
        setMetrics(m);
        setImportance(f.features.filter((row) => row.importance > 0).slice(0, 8));
      } catch (err) {
        if (!cancelled) {
          setHealth("offline");
          setError(err instanceof Error ? err.message : "API unavailable");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const primary = metrics?.lightgbm;
  const attacks = Object.entries(metrics?.per_attack || {});
  const fidelity = metrics?.fidelity;
  const topImportance = Math.max(...importance.map((item) => item.importance), 1e-9);

  return (
    <div className="rise space-y-12">
      <div className="flex items-end justify-between gap-6">
        <div>
          <h1 className="text-4xl font-medium tracking-tight">Command center</h1>
          <p className="mt-2 max-w-xl text-sm text-white/55">
            Holdout metrics for the Blue Team detector. Numbers come from the last train, not a canned slide.
          </p>
        </div>
        <p className="font-mono text-xs uppercase tracking-[0.18em] text-white/40">
          API <span className={health === "ok" ? "text-signal" : "text-white/40"}>{health}</span>
        </p>
      </div>

      {error ? <p className="font-mono text-sm text-signal">{error}</p> : null}

      <section>
        <h2 className="font-mono text-[11px] uppercase tracking-[0.2em] text-white/40">LightGBM</h2>
        <dl className="mt-4 grid grid-cols-2 gap-x-8 gap-y-6 sm:grid-cols-3 lg:grid-cols-6">
          {[
            ["Precision", pct(primary?.precision)],
            ["Recall", pct(primary?.recall)],
            ["F1", pct(primary?.f1)],
            ["PR-AUC", pct(primary?.pr_auc)],
            ["FPR", pct(primary?.fpr)],
            ["LogReg PR-AUC", pct(metrics?.logreg?.pr_auc)],
          ].map(([k, v]) => (
            <div key={k} className="border-t border-white/10 pt-3">
              <dt className="text-xs text-white/45">{k}</dt>
              <dd className="mt-1 font-mono text-2xl">{v}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section>
        <h2 className="font-mono text-[11px] uppercase tracking-[0.2em] text-white/40">Per-attack recall</h2>
        <table className="mt-4 w-full text-left text-sm">
          <thead className="font-mono text-[11px] uppercase tracking-[0.16em] text-white/35">
            <tr>
              <th className="pb-3 font-normal">Attack</th>
              <th className="pb-3 font-normal">Recall</th>
              <th className="pb-3 font-normal">F1</th>
              <th className="pb-3 font-normal">FPR</th>
            </tr>
          </thead>
          <tbody>
            {attacks.length === 0 ? (
              <tr>
                <td colSpan={4} className="py-4 text-white/40">
                  Train the model to populate this table.
                </td>
              </tr>
            ) : (
              attacks.map(([name, row]) => (
                <tr key={name} className="border-t border-white/10">
                  <td className="py-3">{name.replaceAll("_", " ")}</td>
                  <td className="py-3 font-mono">{pct(row.recall)}</td>
                  <td className="py-3 font-mono">{pct(row.f1)}</td>
                  <td className="py-3 font-mono">{pct(row.fpr)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </section>

      <div className="grid gap-12 lg:grid-cols-2">
        <section>
          <h2 className="font-mono text-[11px] uppercase tracking-[0.2em] text-white/40">Feature importance</h2>
          {importance.length === 0 || importance.every((row) => row.importance <= 0) ? (
            <p className="mt-4 text-sm text-white/40">Train the model to populate this chart.</p>
          ) : (
            <ul className="mt-4 space-y-3">
              {importance.map((row) => (
                <li key={row.feature} className="grid grid-cols-[8.5rem_1fr_2.75rem] items-center gap-3">
                  <span className="truncate font-mono text-[11px] text-white/55">
                    {row.feature.replaceAll("_", " ")}
                  </span>
                  <div className="h-1.5 bg-white/10">
                    <div
                      className="h-1.5 bg-signal"
                      style={{ width: `${(row.importance / topImportance) * 100}%` }}
                    />
                  </div>
                  <span className="text-right font-mono text-[11px] text-white/40">
                    {(row.importance * 100).toFixed(1)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
        <section>
          <h2 className="font-mono text-[11px] uppercase tracking-[0.2em] text-white/40">Fidelity</h2>
          <dl className="mt-4 space-y-3 text-sm">
            {[
              ["Amount", fidelity?.amount_distribution],
              ["Time", fidelity?.time_distribution],
              ["Velocity", fidelity?.velocity_distribution],
              ["Merchant", fidelity?.merchant_distribution],
              ["Overall", fidelity?.overall_fidelity],
            ].map(([k, v]) => (
              <div key={String(k)} className="flex justify-between border-b border-white/10 py-2">
                <dt className="text-white/50">{k}</dt>
                <dd className="font-mono">{pct(typeof v === "number" ? v : undefined)}</dd>
              </div>
            ))}
          </dl>
        </section>
      </div>
    </div>
  );
}
