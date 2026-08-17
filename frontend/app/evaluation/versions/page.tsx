"use client";

import { useEffect, useState } from "react";
import { api, type RunSummary } from "@/lib/api";
import { pct } from "@/lib/format";
import { PageTitle, Section } from "@/components/ui";

type Compare = {
  model_a: string;
  model_b: string;
  available_versions: string[];
  runs_a: RunSummary[];
  runs_b: RunSummary[];
  note?: string;
};

export default function ModelVersions() {
  const [data, setData] = useState<Compare | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    void api<Compare>("/evaluation/compare")
      .then(setData)
      .catch((err) => setError(err instanceof Error ? err.message : "Versions unavailable"));
  }, []);

  return (
    <div className="rise space-y-10">
      <PageTitle title="Model Versions">
        Recorded Red Team seeds scored under each detector version. Replay a run to add a row for the current model.
      </PageTitle>
      {error ? <p className="font-mono text-sm text-signal">{error}</p> : null}

      <p className="font-mono text-xs text-white/40">
        {(data?.available_versions || []).join(" · ") || "No scored versions yet."}
      </p>
      {data?.note ? <p className="text-sm text-white/50">{data.note}</p> : null}

      {(["runs_a", "runs_b"] as const).map((key) => {
        const rows = data?.[key] || [];
        const title = key === "runs_a" ? data?.model_a : data?.model_b;
        return (
          <Section key={key} title={title || key}>
            <table className="mt-4 w-full text-left text-sm">
              <thead className="font-mono text-[11px] uppercase tracking-[0.16em] text-white/35">
                <tr>
                  <th className="pb-3 font-normal">Attack</th>
                  <th className="pb-3 font-normal">Detection</th>
                  <th className="pb-3 font-normal">Evasion</th>
                  <th className="pb-3 font-normal">PR-AUC</th>
                </tr>
              </thead>
              <tbody>
                {rows.slice(0, 12).map((row) => (
                  <tr key={row.simulation_id} className="border-t border-white/10">
                    <td className="py-3">{row.attack_name}</td>
                    <td className="py-3 font-mono">{pct(row.detection_rate)}</td>
                    <td className="py-3 font-mono">{pct(row.attack_success)}</td>
                    <td className="py-3 font-mono">{pct(row.pr_auc)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Section>
        );
      })}
    </div>
  );
}
