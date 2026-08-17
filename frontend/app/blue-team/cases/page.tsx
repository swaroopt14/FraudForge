"use client";

import { useEffect, useState } from "react";
import { api, type BlueDetection } from "@/lib/api";
import { familyLabel, pct } from "@/lib/format";
import { PageTitle } from "@/components/ui";

export default function CasesPage() {
  const [rows, setRows] = useState<BlueDetection[]>([]);
  const [tab, setTab] = useState<"stopped" | "bypassed">("stopped");
  const [error, setError] = useState("");

  useEffect(() => {
    api<{ detections: BlueDetection[] }>("/blue/detections")
      .then((body) => setRows(body.detections || []))
      .catch((err: Error) => setError(err.message));
  }, []);

  const stopped = rows.filter((r) => (r.fraud_probability || 0) >= 0.5);
  const bypassed = rows.filter((r) => (r.fraud_probability || 0) < 0.5);
  const shown = tab === "stopped" ? stopped : bypassed;

  return (
    <div className="rise space-y-8">
      <PageTitle title="Stopped / Bypassed">Scored rows from the current Blue ingest. Stopped is ≥ 0.5.</PageTitle>
      {error ? <p className="font-mono text-sm text-signal">{error}</p> : null}
      <div className="flex gap-6 font-mono text-[11px] uppercase tracking-[0.16em]">
        <button type="button" className={tab === "stopped" ? "text-signal" : "text-white/40"} onClick={() => setTab("stopped")}>
          Stopped {stopped.length}
        </button>
        <button type="button" className={tab === "bypassed" ? "text-signal" : "text-white/40"} onClick={() => setTab("bypassed")}>
          Bypassed {bypassed.length}
        </button>
      </div>
      {shown.length === 0 ? (
        <p className="text-sm text-white/40">No rows in this tab. Run a Red Team simulation first.</p>
      ) : (
        <table className="w-full text-left text-sm">
          <thead className="font-mono text-[11px] uppercase tracking-[0.16em] text-white/35">
            <tr>
              <th className="pb-3 font-normal">Transaction</th>
              <th className="pb-3 font-normal">Attack</th>
              <th className="pb-3 font-normal text-right">Risk</th>
              <th className="pb-3 font-normal text-right">Prob</th>
              <th className="pb-3 font-normal text-right">Action</th>
            </tr>
          </thead>
          <tbody>
            {shown.slice(0, 80).map((row) => (
              <tr key={row.transaction_id} className="border-t border-white/10">
                <td className="py-3 font-mono text-[12px]">{row.transaction_id}</td>
                <td className="py-3">{familyLabel(row.attack_prediction)}</td>
                <td className="py-3 text-right font-mono">{row.risk_score}</td>
                <td className="py-3 text-right font-mono">{pct(row.fraud_probability)}</td>
                <td className="py-3 text-right font-mono text-signal">{row.action}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
