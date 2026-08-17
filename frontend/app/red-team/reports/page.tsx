"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, type RunSummary } from "@/lib/api";
import { pct } from "@/lib/format";
import { PageTitle } from "@/components/ui";

export default function AttackReports() {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    void api<{ runs: RunSummary[] }>("/red-team/runs")
      .then((body) => setRuns(body.runs || []))
      .catch((err) => setError(err instanceof Error ? err.message : "Reports unavailable"));
  }, []);

  return (
    <div className="rise space-y-10">
      <PageTitle title="Attack Reports">
        Written findings for each scored run. Open a report to see what Red Team did and what Blue Team missed.
      </PageTitle>
      {error ? <p className="font-mono text-sm text-signal">{error}</p> : null}
      <ul className="divide-y divide-white/10">
        {runs.map((row) => (
          <li key={row.simulation_id} className="py-5">
            <Link href={`/red-team/runs/${row.simulation_id}`} className="block hover:text-signal">
              <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-white/35">{row.simulation_id}</p>
              <p className="mt-1 text-lg">{row.attack_name}</p>
              <p className="mt-1 font-mono text-xs text-white/40">
                {row.difficulty} · detection {pct(row.detection_rate)} · evasion {pct(row.attack_success)}
              </p>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
