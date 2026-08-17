"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { EmptyState } from "@/components/empty-state";
import { api, type BlueReport } from "@/lib/api";

export default function DefenseReports() {
  const [data, setData] = useState<BlueReport | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api<BlueReport>("/blue/reports")
      .then(setData)
      .catch((err: Error) => setError(err.message));
  }, []);

  return (
    <div className="rise space-y-10">
      <div>
        <h1 className="text-4xl font-medium tracking-tight">Defense reports</h1>
        <p className="mt-2 max-w-xl text-sm text-white/55">
          Every Red Team simulation writes a corresponding Blue Team report.
        </p>
      </div>
      {error ? <p className="font-mono text-sm text-signal">{error}</p> : null}
      {!data?.data_available || !data.report ? (
        <EmptyState title="No defense report" body={data?.reason || "Run a Red Team test. The Blue report is generated from that stream."} />
      ) : (
        <>
          <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-white/40">Simulation {data.simulation_id}</p>
          <pre className="overflow-x-auto whitespace-pre-wrap font-mono text-[13px] leading-6 text-white/80">{data.report}</pre>
          <Link
            href="/red-team?attack=mule_network"
            className="inline-block bg-signal px-5 py-3 text-sm font-medium text-ink"
          >
            Generate adaptive attack
          </Link>
        </>
      )}
    </div>
  );
}
