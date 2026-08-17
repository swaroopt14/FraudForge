"use client";

import { useEffect, useMemo, useState } from "react";
import { api, type Confusion, type Metrics, type ThresholdPoint } from "@/lib/api";
import { pct } from "@/lib/format";
import { Kpi, PageTitle, Section } from "@/components/ui";

export default function ModelPerformance() {
  const [holdout, setHoldout] = useState<Metrics | null>(null);
  const [confusion, setConfusion] = useState<Confusion | null>(null);
  const [curve, setCurve] = useState<{ recall: number[]; precision: number[] } | null>(null);
  const [sweep, setSweep] = useState<ThresholdPoint[]>([]);
  const [source, setSource] = useState("");
  const [idx, setIdx] = useState(10);
  const [importance, setImportance] = useState<{ feature: string; importance: number }[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([
      api<{ lightgbm?: Metrics; model_version?: string }>("/model/metrics"),
      api<Confusion>("/model/confusion-matrix"),
      api<{ recall: number[]; precision: number[]; source?: string }>("/model/pr-curve"),
      api<{ sweep: ThresholdPoint[]; source?: string }>("/model/threshold-sweep"),
      api<{ features: { feature: string; importance: number }[] }>("/model/feature-importance"),
    ])
      .then(([m, c, pr, sw, fi]) => {
        setHoldout(m.lightgbm || null);
        setConfusion(c);
        setCurve(pr);
        setSweep(sw.sweep || []);
        setSource(sw.source || pr.source || c.source || "");
        const atHalf = (sw.sweep || []).findIndex((row) => Math.abs((row.threshold || 0) - 0.5) < 0.03);
        setIdx(atHalf >= 0 ? atHalf : Math.floor((sw.sweep || []).length / 2));
        setImportance((fi.features || []).filter((row) => row.importance > 0).slice(0, 10));
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Metrics unavailable"));
  }, []);

  const point = sweep[idx];
  const top = Math.max(...importance.map((r) => r.importance), 1e-9);
  const path = useMemo(() => {
    if (!curve?.recall?.length) return "";
    return curve.recall
      .map((r, i) => {
        const x = 8 + r * 220;
        const y = 8 + (1 - (curve.precision[i] || 0)) * 120;
        return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(" ");
  }, [curve]);

  return (
    <div className="rise space-y-12">
      <PageTitle title="Model Performance">
        Holdout metrics for BLUE-0.1.0. The threshold sweep is an IEEE sample scored by the frozen detector — not the
        Red Team mix set.
      </PageTitle>
      {error ? <p className="font-mono text-sm text-signal">{error}</p> : null}

      <dl className="grid grid-cols-2 gap-x-8 gap-y-6 sm:grid-cols-3 lg:grid-cols-6">
        <Kpi label="Precision" value={pct(holdout?.precision)} hint="holdout @ 0.5" />
        <Kpi label="Recall" value={pct(holdout?.recall)} />
        <Kpi label="F1" value={pct(holdout?.f1)} />
        <Kpi label="PR-AUC" value={pct(holdout?.pr_auc)} />
        <Kpi label="ROC-AUC" value={pct(holdout?.roc_auc)} />
        <Kpi label="False positive rate" value={pct(holdout?.fpr)} />
      </dl>

      <Section title="Confusion matrix @ 0.5">
        <table className="mt-4 text-sm">
          <thead className="font-mono text-[11px] uppercase tracking-[0.16em] text-white/35">
            <tr>
              <th className="pb-3 pr-6 font-normal" />
              <th className="pb-3 pr-6 font-normal">Pred legit</th>
              <th className="pb-3 font-normal">Pred fraud</th>
            </tr>
          </thead>
          <tbody>
            <tr className="border-t border-white/10">
              <td className="py-3 pr-6 text-white/45">Actual legit</td>
              <td className="py-3 pr-6 font-mono">{confusion?.tn ?? "—"}</td>
              <td className="py-3 font-mono">{confusion?.fp ?? "—"}</td>
            </tr>
            <tr className="border-t border-white/10">
              <td className="py-3 pr-6 text-white/45">Actual fraud</td>
              <td className="py-3 pr-6 font-mono">{confusion?.fn ?? "—"}</td>
              <td className="py-3 font-mono">{confusion?.tp ?? "—"}</td>
            </tr>
          </tbody>
        </table>
        <p className="mt-3 font-mono text-[11px] text-white/30">{source}</p>
      </Section>

      <div className="grid gap-12 lg:grid-cols-2">
        <Section title="Precision / recall curve">
          <svg viewBox="0 0 236 136" className="mt-6 w-full max-w-sm text-signal">
            <rect x="8" y="8" width="220" height="120" fill="none" stroke="rgba(255,255,255,0.12)" />
            {path ? <path d={path} fill="none" stroke="currentColor" strokeWidth="1.5" /> : null}
          </svg>
        </Section>
        <Section title="Threshold analysis">
          {point ? (
            <div className="mt-6 space-y-4">
              <input
                type="range"
                min={0}
                max={Math.max(sweep.length - 1, 0)}
                value={idx}
                onChange={(e) => setIdx(Number(e.target.value))}
                className="w-full accent-[#FF5F00]"
              />
              <p className="font-mono text-sm">Threshold {point.threshold?.toFixed(2)}</p>
              <dl className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <dt className="text-white/45">Precision</dt>
                  <dd className="font-mono">{pct(point.precision)}</dd>
                </div>
                <div>
                  <dt className="text-white/45">Recall</dt>
                  <dd className="font-mono">{pct(point.recall)}</dd>
                </div>
                <div>
                  <dt className="text-white/45">F1</dt>
                  <dd className="font-mono">{pct(point.f1)}</dd>
                </div>
                <div>
                  <dt className="text-white/45">FPR</dt>
                  <dd className="font-mono">{pct(point.fpr)}</dd>
                </div>
              </dl>
            </div>
          ) : (
            <p className="mt-4 text-sm text-white/40">Sweep unavailable.</p>
          )}
        </Section>
      </div>

      <Section title="Feature importance">
        <ul className="mt-4 max-w-xl space-y-3">
          {importance.map((row) => (
            <li key={row.feature} className="grid grid-cols-[9rem_1fr_2.75rem] items-center gap-3">
              <span className="truncate font-mono text-[11px] text-white/55">{row.feature.replaceAll("_", " ")}</span>
              <div className="h-1.5 bg-white/10">
                <div className="h-1.5 bg-signal" style={{ width: `${(row.importance / top) * 100}%` }} />
              </div>
              <span className="text-right font-mono text-[11px] text-white/40">{(row.importance * 100).toFixed(1)}</span>
            </li>
          ))}
        </ul>
      </Section>
    </div>
  );
}
