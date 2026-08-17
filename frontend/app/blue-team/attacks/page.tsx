"use client";

import { useEffect, useState } from "react";
import { EmptyState } from "@/components/empty-state";
import { api, type BlueCoverage } from "@/lib/api";
import { familyLabel, familyShort, num, pct } from "@/lib/format";

export default function AttackIntel() {
  const [data, setData] = useState<BlueCoverage | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api<BlueCoverage>("/blue/attack-coverage")
      .then(setData)
      .catch((err: Error) => setError(err.message));
  }, []);

  const dist = Object.entries(data?.distribution || {}).sort((a, b) => b[1] - a[1]);

  return (
    <div className="rise space-y-12">
      <div>
        <h1 className="text-4xl font-medium tracking-tight">Attack intelligence</h1>
        <p className="mt-2 max-w-xl text-sm text-white/55">What families Blue Team is seeing, and what it misses.</p>
      </div>
      {error ? <p className="font-mono text-sm text-signal">{error}</p> : null}
      {!data?.data_available ? (
        <EmptyState title="No identifications yet" body={data?.reason || "Run a simulation so Blue can classify the stream."} />
      ) : (
        <>
          <section>
            <h2 className="font-mono text-[11px] uppercase tracking-[0.2em] text-white/40">Attacks detected</h2>
            <p className="mt-3 font-mono text-4xl">{num(data.attacks_detected)}</p>
          </section>
          <section>
            <h2 className="font-mono text-[11px] uppercase tracking-[0.2em] text-white/40">Family distribution</h2>
            <ul className="mt-4 space-y-3">
              {dist.map(([name, share]) => (
                <li key={name} className="grid grid-cols-[9rem_1fr_3.5rem] items-center gap-3">
                  <span className="truncate text-sm">{familyLabel(name)}</span>
                  <div className="h-1.5 bg-white/10">
                    <div className="h-1.5 bg-signal" style={{ width: `${Math.min(100, share * 100)}%` }} />
                  </div>
                  <span className="text-right font-mono text-[11px] text-white/40">{pct(share)}</span>
                </li>
              ))}
            </ul>
          </section>
          <section>
            <h2 className="font-mono text-[11px] uppercase tracking-[0.2em] text-white/40">Detection matrix</h2>
            <table className="mt-4 w-full text-left text-sm">
              <thead className="font-mono text-[11px] uppercase tracking-[0.16em] text-white/35">
                <tr>
                  <th className="pb-3 font-normal">Family</th>
                  <th className="pb-3 font-normal text-right">Generated</th>
                  <th className="pb-3 font-normal text-right">Detected</th>
                  <th className="pb-3 font-normal text-right">Missed</th>
                </tr>
              </thead>
              <tbody>
                {(data.matrix || []).map((row) => (
                  <tr key={row.family} className="border-t border-white/10">
                    <td className="py-3">
                      <span className="font-mono text-[11px] text-white/40">{familyShort(row.family)}</span>
                      <span className="ml-3">{familyLabel(row.family)}</span>
                    </td>
                    <td className="py-3 text-right font-mono">{num(row.generated)}</td>
                    <td className="py-3 text-right font-mono">{num(row.detected)}</td>
                    <td className="py-3 text-right font-mono">{num(row.missed)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </>
      )}
    </div>
  );
}
