"use client";

import { useEffect, useState } from "react";
import { EmptyState } from "@/components/empty-state";
import { NetworkGraph } from "@/components/network-graph";
import { api, type BlueNetwork } from "@/lib/api";
import { familyLabel, inr, num, pct } from "@/lib/format";

export default function NetworkIntel() {
  const [data, setData] = useState<BlueNetwork | null>(null);
  const [error, setError] = useState("");

  async function load(id?: string) {
    try {
      const path = id ? `/blue/network/${encodeURIComponent(id)}` : "/blue/network";
      setData(await api<BlueNetwork>(path));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Network lookup failed");
    }
  }

  useEffect(() => {
    void load();
  }, []);

  const profile = data?.profile;

  return (
    <div className="rise space-y-12">
      <div>
        <h1 className="text-4xl font-medium tracking-tight">Network intelligence</h1>
        <p className="mt-2 max-w-xl text-sm text-white/55">
          Coordinated fraud is a graph. Individual rows can look legitimate.
        </p>
      </div>
      {error ? <p className="font-mono text-sm text-signal">{error}</p> : null}
      {!data?.data_available ? (
        <EmptyState title="No graph yet" body={data?.reason || "Ingest a stream that shares beneficiaries, devices, or IPs."} />
      ) : (
        <>
          <dl className="grid grid-cols-2 gap-x-8 gap-y-6 sm:grid-cols-5">
            {[
              ["High-risk clusters", num(data.high_risk_clusters)],
              ["Shared devices", num(data.shared_devices)],
              ["Shared IPs", num(data.shared_ips)],
              ["Suspicious beneficiaries", num(data.suspicious_beneficiaries)],
              ["Mule networks", num(data.mule_networks)],
            ].map(([k, v]) => (
              <div key={k} className="border-t border-white/10 pt-3">
                <dt className="text-xs text-white/45">{k}</dt>
                <dd className="mt-1 font-mono text-2xl">{v}</dd>
              </div>
            ))}
          </dl>
          <div className="grid gap-12 lg:grid-cols-[minmax(0,1fr)_minmax(0,260px)]">
            <section>
              <h2 className="font-mono text-[11px] uppercase tracking-[0.2em] text-white/40">Graph</h2>
              <NetworkGraph
                nodes={data.focus?.nodes || []}
                edges={data.focus?.edges || []}
                focus={data.focus?.entity_id}
                onSelect={(id) => void load(id)}
              />
            </section>
            {profile?.found !== false ? (
              <aside>
                <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-white/40">Entity</p>
                <h2 className="mt-2 break-all font-mono text-sm">{profile?.entity_id}</h2>
                <dl className="mt-6 space-y-3 text-sm">
                  {[
                    ["Risk", String(profile?.risk_score ?? "—")],
                    ["Customers", num(profile?.connected_customers)],
                    ["Transactions", num(profile?.transactions)],
                    ["24h volume", inr(profile?.total_value)],
                    ["Devices", num(profile?.devices)],
                    ["IPs", num(profile?.ips)],
                    ["Classification", familyLabel(profile?.classification)],
                    ["Confidence", pct(profile?.confidence)],
                  ].map(([k, v]) => (
                    <div key={k} className="flex justify-between border-b border-white/10 py-2">
                      <dt className="text-white/45">{k}</dt>
                      <dd className="font-mono">{v}</dd>
                    </div>
                  ))}
                </dl>
                <ul className="mt-6">
                  {(profile?.signals || []).map((s) => (
                    <li key={s.signal} className="border-t border-white/10 py-2 text-sm">
                      {s.severity} · {s.signal}
                    </li>
                  ))}
                </ul>
              </aside>
            ) : null}
          </div>
        </>
      )}
    </div>
  );
}
