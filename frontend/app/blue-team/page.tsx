"use client";

import { useEffect, useState } from "react";
import { EmptyState } from "@/components/empty-state";
import { api, type BlueDashboard } from "@/lib/api";
import { familyShort, num, pct } from "@/lib/format";

export default function BlueCommand() {
  const [data, setData] = useState<BlueDashboard | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api<BlueDashboard>("/blue/dashboard")
      .then(setData)
      .catch((err: Error) => setError(err.message));
  }, []);

  const coverage = Object.entries(data?.coverage || {});

  return (
    <div className="rise space-y-12">
      <div>
        <h1 className="text-4xl font-medium tracking-tight">Defense command</h1>
        <p className="mt-2 max-w-xl text-sm text-white/55">
          Observe, detect, identify, investigate, score, and mitigate. Values come from the last Blue ingest, not a slide.
        </p>
      </div>
      {error ? <p className="font-mono text-sm text-signal">{error}</p> : null}
      {!data || !data.data_available ? (
        <EmptyState
          title="No payment stream yet"
          body={data?.reason || "Run a Red Team contextual attack. Blue Team only scores what it observes."}
        />
      ) : (
        <>
          <section>
            <h2 className="font-mono text-[11px] uppercase tracking-[0.2em] text-white/40">Live posture</h2>
            <dl className="mt-4 grid grid-cols-2 gap-x-8 gap-y-6 sm:grid-cols-3 lg:grid-cols-5">
              {[
                ["Transactions", num(data.transactions)],
                ["Threats", num(data.threats)],
                ["Detection", pct(data.detection_rate)],
                ["Precision", pct(data.precision)],
                ["Recall", pct(data.recall)],
                ["F1", pct(data.f1)],
                ["PR-AUC", pct(data.pr_auc)],
                ["False positive", pct(data.fpr)],
                ["Active risk", `${num(data.active_high_risk)} HIGH`],
                ["Model", data.model_id || "BLUE-FRAUD-0.2.0"],
              ].map(([k, v]) => (
                <div key={k} className="border-t border-white/10 pt-3">
                  <dt className="text-xs text-white/45">{k}</dt>
                  <dd className="mt-1 font-mono text-2xl">{v}</dd>
                </div>
              ))}
            </dl>
          </section>
          <section>
            <h2 className="font-mono text-[11px] uppercase tracking-[0.2em] text-white/40">Attack detection coverage</h2>
            {coverage.length === 0 ? (
              <p className="mt-4 text-sm text-white/40">No per-family recall yet.</p>
            ) : (
              <ul className="mt-4 space-y-3">
                {coverage.map(([name, recall]) => (
                  <li key={name} className="grid grid-cols-[3.5rem_1fr_3rem] items-center gap-3">
                    <span className="font-mono text-[11px] text-white/55">{familyShort(name)}</span>
                    <div className="h-1.5 bg-white/10">
                      <div className="h-1.5 bg-signal" style={{ width: `${Math.min(100, recall * 100)}%` }} />
                    </div>
                    <span className="text-right font-mono text-[11px] text-white/40">{pct(recall)}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}
    </div>
  );
}
