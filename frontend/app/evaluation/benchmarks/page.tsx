"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { PageTitle } from "@/components/ui";

type Bench = {
  phase: string;
  status: string;
  checks: { label: string; result: string }[];
  report?: string;
  placeholder?: boolean;
};

export default function Benchmarks() {
  const [bench, setBench] = useState<Bench | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    void api<Bench>("/benchmarks/current")
      .then(setBench)
      .catch((err) => setError(err instanceof Error ? err.message : "Benchmark unavailable"));
  }, []);

  const pass = bench?.status === "PASS";

  return (
    <div className="rise space-y-10">
      <PageTitle title="Benchmarks">
        Phase-gate for the lab. This page reports the last recorded P1 run — it does not invent a pass.
      </PageTitle>
      {error ? <p className="font-mono text-sm text-signal">{error}</p> : null}

      <p className={`font-mono text-2xl ${pass ? "text-signal" : "text-white"}`}>
        {(bench?.phase || "P1").toUpperCase()} STATUS: {bench?.status || "—"}
      </p>
      {!pass && bench?.status && bench.status !== "PASS" ? (
        <p className="text-sm text-white/50">
          {bench.placeholder ? bench.report : "See failing checks below."}
        </p>
      ) : null}

      <ul>
        {(bench?.checks || []).map((c) => (
          <li key={c.label} className="flex justify-between border-t border-white/10 py-3 text-sm">
            <span>{c.label}</span>
            <span className={`font-mono ${c.result === "PASS" ? "text-signal" : "text-white"}`}>{c.result}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
