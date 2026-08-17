"use client";

import { useEffect, useState } from "react";
import { api, type LoopSummary } from "@/lib/api";
import { pct } from "@/lib/format";
import { PageTitle } from "@/components/ui";

export default function LoopPage() {
  const [data, setData] = useState<LoopSummary | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api<LoopSummary>("/loop/summary")
      .then(setData)
      .catch((err: Error) => setError(err.message));
  }, []);

  return (
    <div className="rise space-y-8">
      <PageTitle title="Adversarial round">This run versus the prior run. Empty until a Red Team generate exists.</PageTitle>
      {error ? (
        <p className="max-w-xl text-sm text-white/45">
          Loop API is not on this backend yet ({error}). Generate a P2 mule network, then compare models under Blue Team → Model Evolution.
        </p>
      ) : null}
      {data ? (
        <dl className="grid grid-cols-2 gap-6 sm:grid-cols-4">
          {[
            ["Round", String(data.round ?? "—")],
            ["Blue model", data.blue_model || "—"],
            ["Current detection", pct(data.current && "detection_rate" in data.current ? data.current.detection_rate : undefined)],
            ["Prior detection", pct(data.prior && "detection_rate" in data.prior ? data.prior.detection_rate : undefined)],
          ].map(([k, v]) => (
            <div key={k} className="border-t border-white/10 pt-3">
              <dt className="text-xs text-white/45">{k}</dt>
              <dd className="mt-1 font-mono text-xl">{v}</dd>
            </div>
          ))}
        </dl>
      ) : null}
    </div>
  );
}
