"use client";

import { useEffect, useMemo, useState } from "react";
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, type ScoredRow, type Simulation } from "@/lib/api";

export default function Explorer() {
  const [sim, setSim] = useState<Simulation | null>(null);
  const [selected, setSelected] = useState<ScoredRow | null>(null);
  const [lookup, setLookup] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    const raw = sessionStorage.getItem("last_simulation");
    if (!raw) return;
    try {
      const parsed = JSON.parse(raw) as Simulation;
      setSim(parsed);
      setSelected(parsed.missed_transactions?.[0] || parsed.preview?.[0] || null);
    } catch {
      /* ignore */
    }
  }, []);

  const rows = useMemo(() => {
    if (!sim) return [];
    const missed = sim.missed_transactions || [];
    if (missed.length) return missed;
    return sim.preview || [];
  }, [sim]);

  async function fetchTx(id: string) {
    setError("");
    try {
      const row = await api<ScoredRow>(`/transactions/${encodeURIComponent(id)}`);
      setSelected(row);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Not found");
    }
  }

  return (
    <div className="rise space-y-10">
      <div>
        <h1 className="text-4xl font-medium tracking-tight">Transaction explorer</h1>
        <p className="mt-2 max-w-xl text-sm text-white/55">
          Missed attacks from the last red-team run, with SHAP contributions and the policy decision.
        </p>
      </div>

      <form
        className="flex max-w-md items-end gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          if (lookup.trim()) void fetchTx(lookup.trim());
        }}
      >
        <label className="flex-1 text-xs uppercase tracking-[0.16em] text-white/40">
          Transaction id
          <input
            className="mt-2 w-full border-b border-white/20 bg-transparent py-2 font-mono text-sm outline-none"
            value={lookup}
            onChange={(e) => setLookup(e.target.value)}
            placeholder="low_and_slow-424242-0"
          />
        </label>
        <button type="submit" className="border-b border-signal pb-2 text-sm text-signal">
          Open
        </button>
      </form>
      {error ? <p className="font-mono text-xs text-signal">{error}</p> : null}

      <div className="grid gap-12 lg:grid-cols-[1fr_minmax(0,320px)]">
        <section>
          <h2 className="font-mono text-[11px] uppercase tracking-[0.2em] text-white/40">
            {sim ? `${sim.attack_family} · ${sim.missed} missed` : "No simulation in session"}
          </h2>
          <table className="mt-4 w-full text-left text-sm">
            <thead className="font-mono text-[11px] uppercase tracking-[0.16em] text-white/35">
              <tr>
                <th className="pb-3 font-normal">Id</th>
                <th className="pb-3 font-normal">Amount</th>
                <th className="pb-3 font-normal">Score</th>
                <th className="pb-3 font-normal">Decision</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr
                  key={row.transaction_id}
                  className={`cursor-pointer border-t border-white/10 ${selected?.transaction_id === row.transaction_id ? "text-signal" : ""}`}
                  onClick={() => setSelected(row)}
                >
                  <td className="py-3 font-mono text-xs">{row.transaction_id}</td>
                  <td className="py-3 font-mono">{row.amount?.toFixed?.(2) ?? "—"}</td>
                  <td className="py-3 font-mono">{(row.fraud_probability * 100).toFixed(1)}%</td>
                  <td className="py-3">{row.decision}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        <aside>
          <h2 className="font-mono text-[11px] uppercase tracking-[0.2em] text-white/40">Explanation</h2>
          {selected ? (
            <div className="mt-4 space-y-4">
              <p className="text-sm">
                {selected.decision} · {(selected.fraud_probability * 100).toFixed(1)}%
              </p>
              <p className="font-mono text-xs text-white/40">{selected.transaction_id}</p>
              <div className="h-52">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={(selected.explanation || []).map((e) => ({
                      feature: e.feature,
                      shap: e.shap_value,
                    }))}
                    layout="vertical"
                  >
                    <XAxis type="number" hide />
                    <YAxis
                      type="category"
                      dataKey="feature"
                      width={120}
                      tick={{ fill: "#8a8a8a", fontSize: 11 }}
                    />
                    <Tooltip contentStyle={{ background: "#0A0A0A", border: "1px solid #222" }} />
                    <Bar dataKey="shap" fill="#FF5F00" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          ) : (
            <p className="mt-4 text-sm text-white/40">Select a row or look up an id.</p>
          )}
        </aside>
      </div>
    </div>
  );
}
