"use client";

import { useEffect, useState } from "react";
import { EmptyState } from "@/components/empty-state";
import { api, type BlueMitigation } from "@/lib/api";
import { familyLabel, num } from "@/lib/format";

const ACTIONS = ["BLOCK", "HOLD", "STEP-UP", "REVIEW", "ALLOW"] as const;

export default function MitigationCenter() {
  const [data, setData] = useState<BlueMitigation | null>(null);
  const [selected, setSelected] = useState<string>("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function load() {
    try {
      const body = await api<BlueMitigation>("/blue/mitigation");
      setData(body);
      if (!selected && body.items[0]) setSelected(body.items[0].transaction_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Queue failed");
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function act(action: string, tx = selected) {
    if (!tx) return;
    setMessage("");
    try {
      await api(`/blue/mitigation/${encodeURIComponent(tx)}`, {
        method: "POST",
        body: JSON.stringify({ action: action.replace("-", "_"), reason: `${action} from mitigation center` }),
      });
      setMessage(`${action} recorded on ${tx}`);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Action failed");
    }
  }

  async function isolate() {
    try {
      const body = await api<{ applied: number; beneficiary_id?: string }>("/blue/mitigation/cluster", {
        method: "POST",
        body: JSON.stringify({ action: "HOLD", reason: "Isolate cluster" }),
      });
      setMessage(`Held ${body.applied} payments around ${body.beneficiary_id || "cluster"}`);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Cluster action failed");
    }
  }

  const item = data?.items.find((row) => row.transaction_id === selected);

  return (
    <div className="rise space-y-12">
      <div>
        <h1 className="text-4xl font-medium tracking-tight">Mitigation</h1>
        <p className="mt-2 max-w-xl text-sm text-white/55">Blue Team does not only detect. It decides.</p>
      </div>
      {error ? <p className="font-mono text-sm text-signal">{error}</p> : null}
      {!data || data.items.length === 0 ? (
        <EmptyState title="Empty queue" body="Score a stream before there is anything to block, hold, or review." />
      ) : (
        <>
          <dl className="grid grid-cols-2 gap-x-8 gap-y-6 sm:grid-cols-4">
            {["Critical", "High", "Medium", "Low"].map((band) => (
              <div key={band} className="border-t border-white/10 pt-3">
                <dt className="text-xs text-white/45">{band}</dt>
                <dd className="mt-1 font-mono text-2xl">{num(data.counts[band])}</dd>
              </div>
            ))}
          </dl>
          <div className="grid gap-12 lg:grid-cols-[minmax(0,1fr)_minmax(0,280px)]">
            <table className="w-full text-left text-sm">
              <thead className="font-mono text-[11px] uppercase tracking-[0.16em] text-white/35">
                <tr>
                  <th className="pb-3 font-normal">Transaction</th>
                  <th className="pb-3 font-normal">Attack</th>
                  <th className="pb-3 font-normal text-right">Risk</th>
                  <th className="pb-3 font-normal text-right">Recommended</th>
                </tr>
              </thead>
              <tbody>
                {data.items.slice(0, 60).map((row) => (
                  <tr
                    key={row.transaction_id}
                    className={`cursor-pointer border-t border-white/10 ${selected === row.transaction_id ? "text-white" : "text-white/65"}`}
                    onClick={() => setSelected(row.transaction_id)}
                  >
                    <td className="py-3 font-mono text-[12px]">{row.transaction_id}</td>
                    <td className="py-3">{familyLabel(row.attack)}</td>
                    <td className="py-3 text-right font-mono">{row.risk_score}</td>
                    <td className="py-3 text-right font-mono text-signal">{row.recommended}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <aside>
              {item ? (
                <>
                  <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-white/40">{item.transaction_id}</p>
                  <p className="mt-3 text-3xl font-medium">{item.risk_score}</p>
                  <p className="mt-2 text-sm text-white/55">{familyLabel(item.attack)}</p>
                  <div className="mt-6 grid grid-cols-2 gap-2">
                    {ACTIONS.map((action) => (
                      <button
                        key={action}
                        type="button"
                        className="border border-white/15 py-2 text-xs uppercase tracking-[0.14em] hover:border-signal"
                        onClick={() => void act(action)}
                      >
                        {action}
                      </button>
                    ))}
                  </div>
                </>
              ) : null}
              {data.cluster ? (
                <section className="mt-10 border-t border-white/10 pt-6">
                  <h2 className="font-mono text-[11px] uppercase tracking-[0.2em] text-white/40">Cluster action</h2>
                  <p className="mt-3 text-sm text-white/70">
                    {data.cluster.accounts} accounts · {data.cluster.devices} devices · {data.cluster.ips} IPs · 1 beneficiary
                  </p>
                  <button type="button" className="mt-4 w-full bg-signal py-3 text-sm font-medium text-ink" onClick={() => void isolate()}>
                    Isolate cluster
                  </button>
                </section>
              ) : null}
              {message ? <p className="mt-4 font-mono text-xs text-signal">{message}</p> : null}
            </aside>
          </div>
        </>
      )}
    </div>
  );
}
