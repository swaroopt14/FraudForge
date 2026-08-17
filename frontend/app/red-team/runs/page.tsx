"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, type RunSummary } from "@/lib/api";
import { num, pct } from "@/lib/format";
import { PageTitle } from "@/components/ui";

export default function AttackRuns() {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    void api<{ runs: RunSummary[] }>("/red-team/runs")
      .then((body) => setRuns(body.runs || []))
      .catch((err) => setError(err instanceof Error ? err.message : "Runs unavailable"));
  }, []);

  return (
    <div className="rise space-y-10">
      <PageTitle title="Attack Runs">Every scored simulation, newest first. Open a run to see misses, signals, and the report.</PageTitle>
      {error ? <p className="font-mono text-sm text-signal">{error}</p> : null}
      <table className="w-full text-left text-sm">
        <thead className="font-mono text-[11px] uppercase tracking-[0.16em] text-white/35">
          <tr>
            <th className="pb-3 font-normal">Run id</th>
            <th className="pb-3 font-normal">Attack</th>
            <th className="pb-3 font-normal">Difficulty</th>
            <th className="pb-3 font-normal">Scale</th>
            <th className="pb-3 font-normal">Detection</th>
            <th className="pb-3 font-normal">Evasion</th>
            <th className="pb-3 font-normal">Model</th>
          </tr>
        </thead>
        <tbody>
          {runs.length === 0 ? (
            <tr>
              <td colSpan={7} className="py-6 text-white/40">
                No runs yet. Launch one from Red Team Lab.
              </td>
            </tr>
          ) : (
            runs.map((row) => (
              <tr key={row.simulation_id} className="border-t border-white/10">
                <td className="py-3 font-mono text-xs">
                  <Link href={`/red-team/runs/${row.simulation_id}`} className="hover:text-signal">
                    {row.simulation_id}
                  </Link>
                </td>
                <td className="py-3">{row.attack_name}</td>
                <td className="py-3">{row.difficulty}</td>
                <td className="py-3 font-mono">{num(row.scale)}</td>
                <td className="py-3 font-mono">{pct(row.detection_rate)}</td>
                <td className="py-3 font-mono">{pct(row.attack_success)}</td>
                <td className="py-3 font-mono text-[11px] text-white/45">{row.model_version}</td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
