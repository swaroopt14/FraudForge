"use client";

import { useEffect, useState } from "react";
import { api, type LeaderboardRow } from "@/lib/api";
import { num, pct } from "@/lib/format";
import { Kpi, PageTitle, Section } from "@/components/ui";

type Summary = {
  red: { generated: number; variants: number; fidelity: number | null; runs: number };
  blue: {
    detected: number;
    missed: number;
    precision: number;
    recall: number;
    f1: number;
    model_version: string;
  };
  leaderboard: LeaderboardRow[];
};

type FamilyRow = {
  family: string;
  attack_id?: string;
  generated: number;
  detected: number;
  classified: number | null;
  recall: number;
  identification_recall?: number | null;
};

type ModelBlock = {
  model_id: string;
  model_version?: string;
  n_features?: number;
  binary?: { precision?: number; recall?: number; f1?: number; pr_auc?: number; fpr?: number };
  macro_f1?: number | null;
  families: FamilyRow[];
};

type Coverage = {
  seed: number | null;
  n_each: number | null;
  baseline: ModelBlock;
  candidate: ModelBlock | null;
  engineering_targets?: Record<string, number | string>;
  note?: string;
};

function CoverageBars({ rows }: { rows: FamilyRow[] }) {
  return (
    <div className="mt-6 space-y-3">
      {rows.map((row) => (
        <div key={row.family} className="grid grid-cols-[7rem_1fr_4rem] items-center gap-3 text-sm">
          <span className="font-mono text-[11px] uppercase tracking-[0.14em] text-white/45">
            {row.attack_id || row.family}
          </span>
          <div className="h-1.5 bg-white/10">
            <div className="h-1.5 bg-signal" style={{ width: `${Math.min(100, row.recall * 100)}%` }} />
          </div>
          <span className="font-mono text-xs text-right">{pct(row.recall)}</span>
        </div>
      ))}
    </div>
  );
}

export default function RedVsBlue() {
  const [data, setData] = useState<Summary | null>(null);
  const [coverage, setCoverage] = useState<Coverage | null>(null);
  const [p2, setP2] = useState<{
    available?: boolean;
    note?: string;
    improvement?: Record<string, { p1?: number; p2?: number; delta?: number }>;
    p1?: { model_id?: string; binary?: Record<string, number> };
    p2?: { model_id?: string; binary?: Record<string, number> };
  } | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    void api<Summary>("/evaluation/summary")
      .then(setData)
      .catch((err) => setError(err instanceof Error ? err.message : "Evaluation unavailable"));
    void api<Coverage>("/evaluation/attack-coverage")
      .then(setCoverage)
      .catch(() => undefined);
    void api("/evaluation/p1-vs-p2")
      .then(setP2)
      .catch(() => undefined);
  }, []);

  const red = data?.red;
  const blue = data?.blue;
  const families = coverage?.candidate?.families || coverage?.baseline?.families || [];
  const compare = coverage?.candidate && coverage.baseline;

  return (
    <div className="rise space-y-12">
      <PageTitle title="Red vs Blue">
        Recorded attack runs against the frozen detector. Failures stay visible — they are the product.
      </PageTitle>
      {error ? <p className="font-mono text-sm text-signal">{error}</p> : null}

      <div className="grid gap-12 lg:grid-cols-2">
        <Section title="Red Team">
          <dl className="mt-6 grid grid-cols-2 gap-6">
            <Kpi label="Generated" value={num(red?.generated)} />
            <Kpi label="Variants" value={num(red?.variants)} />
            <Kpi label="Fidelity" value={pct(red?.fidelity)} />
            <Kpi label="Runs" value={num(red?.runs)} />
          </dl>
        </Section>
        <Section title="Blue Team">
          <dl className="mt-6 grid grid-cols-2 gap-6">
            <Kpi label="Detected" value={num(blue?.detected)} hint="estimated from run detection × scale" />
            <Kpi label="Missed" value={num(blue?.missed)} />
            <Kpi label="Precision" value={pct(blue?.precision)} hint="IEEE holdout" />
            <Kpi label="Recall" value={pct(blue?.recall)} hint="IEEE holdout" />
            <Kpi label="F1" value={pct(blue?.f1)} />
            <Kpi label="Model" value={blue?.model_version?.split("-hist")[0] || "—"} />
          </dl>
        </Section>
      </div>

      <Section title="Attack coverage">
        <p className="mt-3 max-w-xl text-sm text-white/45">
          Generated / detected / classified per family on a fixed seed. BLUE-0.1.0 is the frozen Round 0 miss. The
          candidate is the latest trained detector (BLUE-0.2.0 after P2 training). Mix-set PR-AUC is not the headline.
        </p>
        {families.length ? <CoverageBars rows={families} /> : <p className="mt-4 text-sm text-white/40">No coverage table yet.</p>}
        {families.length ? (
          <table className="mt-8 w-full text-left text-sm">
            <thead className="font-mono text-[11px] uppercase tracking-[0.16em] text-white/35">
              <tr>
                <th className="pb-3 font-normal">Attack</th>
                <th className="pb-3 font-normal">Generated</th>
                <th className="pb-3 font-normal">Detected</th>
                <th className="pb-3 font-normal">Classified</th>
                <th className="pb-3 font-normal">Recall</th>
              </tr>
            </thead>
            <tbody>
              {families.map((row) => (
                <tr key={row.family} className="border-t border-white/10">
                  <td className="py-3 font-mono text-xs uppercase">{row.family}</td>
                  <td className="py-3 font-mono">{num(row.generated)}</td>
                  <td className="py-3 font-mono">{num(row.detected)}</td>
                  <td className="py-3 font-mono">{row.classified == null ? "—" : num(row.classified)}</td>
                  <td className="py-3 font-mono">{pct(row.recall)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : null}
        {compare ? (
          <p className="mt-4 font-mono text-[11px] text-white/35">
            {coverage?.baseline.model_id} → {coverage?.candidate?.model_id}
            {coverage?.candidate?.binary?.recall != null
              ? ` · attack-mix recall ${pct(coverage.baseline.binary?.recall)} → ${pct(coverage.candidate.binary.recall)}`
              : ""}
            {coverage?.candidate?.macro_f1 != null ? ` · macro F1 ${pct(coverage.candidate.macro_f1)}` : ""}
          </p>
        ) : null}
        {coverage?.note ? <p className="mt-3 text-xs text-white/35">{coverage.note}</p> : null}
      </Section>

      <Section title="Model improvement · P1 vs P2">
        <p className="mt-3 max-w-xl text-sm text-white/45">
          Same attack mix. BLUE-0.1.2 is the row-level detector; BLUE-0.2.0 adds geo, device, IP, and beneficiary graph
          features. These numbers are measured, not targets.
        </p>
        {p2?.available && p2.improvement ? (
          <table className="mt-6 w-full text-left text-sm">
            <thead className="font-mono text-[11px] uppercase tracking-[0.16em] text-white/35">
              <tr>
                <th className="pb-3 font-normal">Metric</th>
                <th className="pb-3 font-normal">P1</th>
                <th className="pb-3 font-normal">P2</th>
                <th className="pb-3 font-normal">Delta</th>
              </tr>
            </thead>
            <tbody>
              {[
                ["Recall", "recall"],
                ["Precision", "precision"],
                ["F1", "f1"],
                ["PR-AUC", "pr_auc"],
                ["FPR", "fpr"],
                ["Mule detection", "mule_detection"],
                ["Beneficiary", "beneficiary"],
                ["Shared device", "shared_device"],
                ["Geo", "geo"],
              ].map(([label, key]) => {
                const row = p2.improvement?.[key];
                return (
                  <tr key={key} className="border-t border-white/10">
                    <td className="py-3">{label}</td>
                    <td className="py-3 font-mono">{pct(row?.p1)}</td>
                    <td className="py-3 font-mono">{pct(row?.p2)}</td>
                    <td className="py-3 font-mono">{row?.delta == null ? "—" : pct(row.delta)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        ) : (
          <p className="mt-4 text-sm text-white/40">{p2?.note || "Train BLUE-0.2.0 to populate this table."}</p>
        )}
      </Section>

      <Section title="Attack matrix">
        <table className="mt-4 w-full text-left text-sm">
          <thead className="font-mono text-[11px] uppercase tracking-[0.16em] text-white/35">
            <tr>
              <th className="pb-3 font-normal">Attack</th>
              <th className="pb-3 font-normal">Generated</th>
              <th className="pb-3 font-normal">Detected</th>
              <th className="pb-3 font-normal">Evasion</th>
              <th className="pb-3 font-normal">Fidelity</th>
              <th className="pb-3 font-normal">Difficulty</th>
            </tr>
          </thead>
          <tbody>
            {(data?.leaderboard || []).map((row) => (
              <tr key={row.attack_id} className="border-t border-white/10">
                <td className="py-3">{row.name}</td>
                <td className="py-3 font-mono">{num(row.scale)}</td>
                <td className="py-3 font-mono">{pct(row.detection_rate)}</td>
                <td className="py-3 font-mono">{pct(row.evasion ?? row.attack_success)}</td>
                <td className="py-3 font-mono">{pct(row.fidelity)}</td>
                <td className="py-3">{row.difficulty}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Section>
    </div>
  );
}
