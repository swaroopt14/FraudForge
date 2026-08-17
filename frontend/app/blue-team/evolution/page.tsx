"use client";

import { useEffect, useState } from "react";
import { EmptyState } from "@/components/empty-state";
import { api, type BlueCompare } from "@/lib/api";
import { familyLabel, pct } from "@/lib/format";

export default function ModelEvolution() {
  const [data, setData] = useState<BlueCompare | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api<BlueCompare>("/blue/models/compare")
      .then(setData)
      .catch((err: Error) => setError(err.message));
  }, []);

  const hold = data?.holdout;
  const families = Object.entries(data?.coordinated_attacks || {});

  return (
    <div className="rise space-y-12">
      <div>
        <h1 className="text-4xl font-medium tracking-tight">Model evolution</h1>
        <p className="mt-2 max-w-xl text-sm text-white/55">
          BLUE-0.1.0 scored rows in isolation. BLUE-0.2.0 adds geo, device, IP, beneficiary, and graph context.
        </p>
      </div>
      {error ? <p className="font-mono text-sm text-signal">{error}</p> : null}
      {!data?.data_available ? (
        <EmptyState title="BLUE-0.2.0 is not trained" body={data?.reason || "Train the P2 models, then compare holdout and coordinated-attack recall."} />
      ) : (
        <>
          <section>
            <h2 className="font-mono text-[11px] uppercase tracking-[0.2em] text-white/40">Holdout</h2>
            <table className="mt-4 w-full text-left text-sm">
              <thead className="font-mono text-[11px] uppercase tracking-[0.16em] text-white/35">
                <tr>
                  <th className="pb-3 font-normal">Metric</th>
                  <th className="pb-3 font-normal">{data.baseline}</th>
                  <th className="pb-3 font-normal">{data.candidate}</th>
                </tr>
              </thead>
              <tbody>
                {(
                  [
                    ["Recall", hold?.p0?.recall, hold?.p2?.recall],
                    ["Precision", hold?.p0?.precision, hold?.p2?.precision],
                    ["F1", hold?.p0?.f1, hold?.p2?.f1],
                    ["PR-AUC", hold?.p0?.pr_auc, hold?.p2?.pr_auc],
                    ["FPR", hold?.p0?.fpr, hold?.p2?.fpr],
                  ] as const
                ).map(([label, a, b]) => (
                  <tr key={label} className="border-t border-white/10">
                    <td className="py-3">{label}</td>
                    <td className="py-3 font-mono">{pct(a)}</td>
                    <td className="py-3 font-mono text-signal">{pct(b)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
          <section>
            <h2 className="font-mono text-[11px] uppercase tracking-[0.2em] text-white/40">Coordinated attacks</h2>
            {families.length === 0 ? (
              <p className="mt-4 text-sm text-white/40">No P0 vs P2 family comparison yet.</p>
            ) : (
              <table className="mt-4 w-full text-left text-sm">
                <thead className="font-mono text-[11px] uppercase tracking-[0.16em] text-white/35">
                  <tr>
                    <th className="pb-3 font-normal">Family</th>
                    <th className="pb-3 font-normal">BLUE-0.1</th>
                    <th className="pb-3 font-normal">BLUE-0.2</th>
                  </tr>
                </thead>
                <tbody>
                  {families.map(([name, row]) => (
                    <tr key={name} className="border-t border-white/10">
                      <td className="py-3">{familyLabel(name)}</td>
                      <td className="py-3 font-mono">{pct(row.p0_recall)}</td>
                      <td className="py-3 font-mono text-signal">{pct(row.p2_recall)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
        </>
      )}
    </div>
  );
}
