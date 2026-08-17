"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { api, type ThreatCard } from "@/lib/api";
import { label } from "@/lib/format";
import { PageTitle } from "@/components/ui";

const FILTERS = [
  { key: "category", label: "Category" },
  { key: "status", label: "Status" },
  { key: "evidence", label: "Evidence" },
  { key: "difficulty", label: "Difficulty" },
] as const;

export default function ThreatLibrary() {
  const [threats, setThreats] = useState<ThreatCard[]>([]);
  const [error, setError] = useState("");
  const [filters, setFilters] = useState({
    category: "",
    status: "",
    evidence: "",
    difficulty: "",
    simulation_ready: "true",
  });

  useEffect(() => {
    void api<{ threats: ThreatCard[] }>("/threats")
      .then((body) => setThreats(body.threats || []))
      .catch((err) => setError(err instanceof Error ? err.message : "Threats unavailable"));
  }, []);

  const options = useMemo(() => {
    return {
      category: [...new Set(threats.map((t) => t.category).filter(Boolean))],
      status: [...new Set(threats.map((t) => t.status).filter(Boolean))],
      evidence: [...new Set(threats.map((t) => t.evidence || t.evidence_level).filter(Boolean))],
      difficulty: [...new Set(threats.flatMap((t) => t.supported_difficulties || []))],
    };
  }, [threats]);

  const rows = threats.filter((t) => {
    if (filters.category && t.category !== filters.category) return false;
    if (filters.status && t.status !== filters.status) return false;
    if (filters.evidence && (t.evidence || t.evidence_level) !== filters.evidence) return false;
    if (filters.difficulty && !(t.supported_difficulties || []).includes(filters.difficulty)) return false;
    if (filters.simulation_ready === "true" && t.simulation_ready === false) return false;
    return true;
  });

  return (
    <div className="rise space-y-10">
      <PageTitle title="Threat Library">
        Attacks are not sampled at random. Each family is an explicit definition with variants, difficulty, and
        hypothesized detection signals.
      </PageTitle>
      {error ? <p className="font-mono text-sm text-signal">{error}</p> : null}

      <div className="flex flex-wrap gap-6">
        {FILTERS.map((f) => (
          <label key={f.key} className="text-xs uppercase tracking-[0.16em] text-white/40">
            {f.label}
            <select
              className="mt-2 block border-b border-white/20 bg-transparent py-1.5 text-sm outline-none"
              value={filters[f.key]}
              onChange={(e) => setFilters((prev) => ({ ...prev, [f.key]: e.target.value }))}
            >
              <option value="" className="bg-ink">
                All
              </option>
              {options[f.key].map((value) => (
                <option key={value} value={value} className="bg-ink">
                  {label(value)}
                </option>
              ))}
            </select>
          </label>
        ))}
        <label className="text-xs uppercase tracking-[0.16em] text-white/40">
          Simulation ready
          <select
            className="mt-2 block border-b border-white/20 bg-transparent py-1.5 text-sm outline-none"
            value={filters.simulation_ready}
            onChange={(e) => setFilters((prev) => ({ ...prev, simulation_ready: e.target.value }))}
          >
            <option value="true" className="bg-ink">
              Ready
            </option>
            <option value="" className="bg-ink">
              All
            </option>
          </select>
        </label>
      </div>

      <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-white/35">
        {rows.length} threats · {rows.reduce((n, t) => n + (t.variant_count || t.variants?.length || 0), 0)} variants
      </p>

      <div className="grid gap-8 md:grid-cols-2">
        {rows.map((t) => (
          <Link
            key={t.attack_id}
            href={`/threats/${t.attack_id}`}
            className="block border-t border-white/10 pt-4 hover:border-signal"
          >
            <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-signal">{t.attack_id}</p>
            <h2 className="mt-2 text-xl font-medium">{t.name}</h2>
            <p className="mt-1 text-sm text-white/45">
              {label(t.category)} · {label(t.evidence || t.evidence_level)}
            </p>
            <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
              <div>
                <dt className="text-xs text-white/35">Difficulty</dt>
                <dd className="font-mono">{(t.supported_difficulties || []).join(" / ") || "—"}</dd>
              </div>
              <div>
                <dt className="text-xs text-white/35">Simulation</dt>
                <dd className="font-mono">{t.simulation_ready ? "READY" : "NO"}</dd>
              </div>
              <div className="col-span-2">
                <dt className="text-xs text-white/35">Signals</dt>
                <dd className="mt-1 text-white/70">{(t.detection_signals || []).slice(0, 4).join(", ") || "—"}</dd>
              </div>
              <div>
                <dt className="text-xs text-white/35">Variants</dt>
                <dd className="font-mono">{t.variant_count ?? t.variants?.length ?? 0}</dd>
              </div>
            </dl>
          </Link>
        ))}
      </div>

      <table className="w-full text-left text-sm">
        <thead className="font-mono text-[11px] uppercase tracking-[0.16em] text-white/35">
          <tr>
            <th className="pb-3 font-normal">ID</th>
            <th className="pb-3 font-normal">Threat</th>
            <th className="pb-3 font-normal">Category</th>
            <th className="pb-3 font-normal">Evidence</th>
            <th className="pb-3 font-normal">Variants</th>
            <th className="pb-3 font-normal">Difficulty</th>
            <th className="pb-3 font-normal">Simulation</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((t) => (
            <tr key={`row-${t.attack_id}`} className="border-t border-white/10">
              <td className="py-3 font-mono text-xs">
                <Link href={`/threats/${t.attack_id}`} className="hover:text-signal">
                  {t.attack_id}
                </Link>
              </td>
              <td className="py-3">{t.name}</td>
              <td className="py-3">{label(t.category)}</td>
              <td className="py-3">{label(t.evidence || t.evidence_level)}</td>
              <td className="py-3 font-mono">{t.variant_count ?? t.variants?.length ?? 0}</td>
              <td className="py-3 font-mono text-[11px]">{(t.supported_difficulties || []).join(", ")}</td>
              <td className="py-3 font-mono text-[11px]">{t.simulation_ready ? "Ready" : "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
