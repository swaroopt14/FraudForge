"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { api, type ThreatDetail } from "@/lib/api";
import { label } from "@/lib/format";
import { PageTitle, Section } from "@/components/ui";

export default function ThreatDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [threat, setThreat] = useState<ThreatDetail | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!id) return;
    void api<ThreatDetail>(`/threats/${id}`)
      .then(setThreat)
      .catch((err) => setError(err instanceof Error ? err.message : "Not found"));
  }, [id]);

  return (
    <div className="rise space-y-10">
      <PageTitle title={threat?.name || id}>
        {threat?.objective || "Loading threat definition."}
      </PageTitle>
      {error ? <p className="font-mono text-sm text-signal">{error}</p> : null}
      {threat ? (
        <>
          <dl className="grid grid-cols-2 gap-x-8 gap-y-6 sm:grid-cols-4">
            {[
              ["ID", threat.attack_id],
              ["Category", label(threat.category)],
              ["Evidence", label(threat.evidence)],
              ["Variants", String(threat.variants)],
              ["Template", threat.simulation_template],
              ["Family", label(threat.family)],
              ["Simulation", threat.simulation_ready ? "READY" : "NO"],
              ["Difficulty", threat.supported_difficulties.join(" / ")],
            ].map(([k, v]) => (
              <div key={k} className="border-t border-white/10 pt-3">
                <dt className="text-xs text-white/45">{k}</dt>
                <dd className="mt-1 font-mono text-sm">{v}</dd>
              </div>
            ))}
          </dl>
          <Section title="Detection signals">
            <ul className="mt-4 max-w-xl">
              {threat.detection_signals.map((s) => (
                <li key={s} className="border-t border-white/10 py-2.5 text-sm">
                  {s}
                </li>
              ))}
            </ul>
          </Section>
          <Section title="Variants">
            <ul className="mt-4 max-w-xl">
              {threat.variant_list.map((v) => (
                <li key={v.id} className="border-t border-white/10 py-2.5 text-sm">
                  <span className="font-mono text-xs text-white/40">{v.id}</span>
                  <span className="ml-3">{v.name}</span>
                </li>
              ))}
            </ul>
          </Section>
          {threat.expected_mitigation ? (
            <Section title="Expected mitigation">
              <p className="mt-4 max-w-xl text-sm text-white/60">{threat.expected_mitigation}</p>
            </Section>
          ) : null}
          <Link
            href={`/red-team?attack=${threat.attack_id}`}
            className="inline-block bg-signal px-6 py-3 text-sm font-medium text-ink"
          >
            Run in Red Team Lab
          </Link>
        </>
      ) : null}
    </div>
  );
}
