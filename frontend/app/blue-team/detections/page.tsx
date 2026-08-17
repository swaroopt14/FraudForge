"use client";

import { useEffect, useState } from "react";
import { EmptyState } from "@/components/empty-state";
import { api, type BlueDetection, type BlueDetectionDetail } from "@/lib/api";
import { familyLabel, pct } from "@/lib/format";

export default function LiveDetection() {
  const [rows, setRows] = useState<BlueDetection[]>([]);
  const [detail, setDetail] = useState<BlueDetectionDetail | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api<{ detections: BlueDetection[] }>("/blue/detections")
      .then((body) => {
        setRows(body.detections);
        if (body.detections[0]) void load(body.detections[0].transaction_id);
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  async function load(id: string) {
    try {
      setDetail(await api<BlueDetectionDetail>(`/blue/detections/${encodeURIComponent(id)}`));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Lookup failed");
    }
  }

  return (
    <div className="rise grid gap-12 lg:grid-cols-[minmax(0,1fr)_minmax(0,280px)]">
      <div>
        <h1 className="text-4xl font-medium tracking-tight">Live detection</h1>
        <p className="mt-2 max-w-xl text-sm text-white/55">
          Blue Team scoring the current stream: family, risk, confidence, action.
        </p>
        {error ? <p className="mt-4 font-mono text-sm text-signal">{error}</p> : null}
        {rows.length === 0 ? (
          <EmptyState title="Nothing on the wire" body="Generate a Red Team simulation. Detection only exists after ingest." />
        ) : (
          <table className="mt-8 w-full text-left text-sm">
            <thead className="font-mono text-[11px] uppercase tracking-[0.16em] text-white/35">
              <tr>
                <th className="pb-3 font-normal">Time</th>
                <th className="pb-3 font-normal">Transaction</th>
                <th className="pb-3 font-normal">Attack</th>
                <th className="pb-3 font-normal text-right">Risk</th>
                <th className="pb-3 font-normal text-right">Conf</th>
                <th className="pb-3 font-normal text-right">Action</th>
              </tr>
            </thead>
            <tbody>
              {rows.slice(0, 80).map((row) => (
                <tr
                  key={row.transaction_id}
                  className={`cursor-pointer border-t border-white/10 ${detail?.transaction_id === row.transaction_id ? "text-white" : "text-white/70"}`}
                  onClick={() => void load(row.transaction_id)}
                >
                  <td className="py-3 font-mono text-[12px]">{row.clock || "—"}</td>
                  <td className="py-3 font-mono text-[12px]">{row.transaction_id}</td>
                  <td className="py-3">{familyLabel(row.attack_prediction)}</td>
                  <td className="py-3 text-right font-mono">{row.risk_score}</td>
                  <td className="py-3 text-right font-mono">{pct(row.classification_confidence)}</td>
                  <td className="py-3 text-right font-mono text-signal">{row.action}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      {detail ? (
        <aside>
          <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-white/40">Transaction</p>
          <h2 className="mt-2 break-all font-mono text-sm">{detail.transaction_id}</h2>
          <dl className="mt-6 space-y-3 text-sm">
            {[
              ["Risk score", String(detail.risk_score ?? "—")],
              ["Fraud probability", detail.fraud_probability?.toFixed(2) ?? "—"],
              ["Attack", familyLabel(detail.attack_classification)],
              ["Confidence", pct(detail.classification_confidence)],
              ["Decision", detail.action || "—"],
            ].map(([k, v]) => (
              <div key={k} className="flex justify-between border-b border-white/10 py-2">
                <dt className="text-white/45">{k}</dt>
                <dd className="font-mono">{v}</dd>
              </div>
            ))}
          </dl>
          <h3 className="mt-8 font-mono text-[11px] uppercase tracking-[0.2em] text-white/40">Detected signals</h3>
          <ul className="mt-3">
            {(detail.signals || []).length ? (
              (detail.signals || []).map((s) => (
                <li key={s.signal} className="border-t border-white/10 py-2.5 text-sm">
                  {s.signal}
                  <span className="ml-2 font-mono text-[11px] text-white/35">{s.severity}</span>
                </li>
              ))
            ) : (
              <li className="text-sm text-white/40">No contextual signals fired.</li>
            )}
          </ul>
          <p className="mt-6 text-[15px] leading-6 text-white/70">{detail.reason}</p>
        </aside>
      ) : null}
    </div>
  );
}
