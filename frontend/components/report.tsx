import { parseNarrative, pct } from "@/lib/report";
import type { Simulation } from "@/lib/api";

function SignalList({ title, items }: { title: string; items: string[] }) {
  return (
    <div>
      <h4 className="font-mono text-[11px] uppercase tracking-[0.2em] text-white/40">{title}</h4>
      {items.length ? (
        <ul className="mt-3">
          {items.map((item) => (
            <li key={item} className="border-t border-white/10 py-2.5 text-[15px] leading-6 text-white">
              {item}
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-3 text-sm text-white/40">None listed.</p>
      )}
    </div>
  );
}

export function ReportPane({ result }: { result: Simulation }) {
  const narrative = parseNarrative(result.report, result.narrative);
  const metrics = result.metrics || {};
  const detection = result.detection_rate ?? metrics.recall ?? 0;
  const detected = result.detected ?? Math.max(0, result.generated - result.missed);

  return (
    <article key={result.simulation_id} className="rise mt-6">
      <div className="h-0.5 w-10 bg-signal" />
      <p className="mt-6 font-mono text-[11px] uppercase tracking-[0.2em] text-white/40">
        Run {result.simulation_id}
      </p>
      <h3 className="mt-3 text-3xl font-medium tracking-tight">
        {(result.attack_family || "attack").replaceAll("_", " ")}
      </h3>
      <p className="mt-3 text-[15px] text-white/55">
        <span className="font-mono text-white">{result.missed.toLocaleString()}</span> missed
        <span className="text-white/25"> · </span>
        <span className="font-mono text-white/80">{detected.toLocaleString()}</span> caught
        <span className="text-white/25"> · </span>
        {result.generated.toLocaleString()} generated
      </p>

      <div className="mt-8 max-w-xl">
        <div className="flex items-baseline justify-between gap-4">
          <span className="font-mono text-[11px] uppercase tracking-[0.2em] text-white/40">Detection</span>
          <span className="font-mono text-2xl text-signal">{pct(detection)}</span>
        </div>
        <div className="mt-3 h-2 bg-white/15">
          <div
            className="h-2 bg-signal transition-[width] duration-700 ease-out"
            style={{ width: `${Math.max(detection > 0 ? 1.5 : 0, Math.min(100, detection * 100))}%` }}
          />
        </div>
      </div>

      <dl className="mt-10 grid grid-cols-2 gap-x-8 gap-y-6 sm:grid-cols-3">
        {[
          ["Precision", pct(metrics.precision)],
          ["Recall", pct(metrics.recall)],
          ["F1", pct(metrics.f1)],
          ["PR-AUC", pct(metrics.pr_auc)],
          ["FPR", pct(metrics.fpr)],
        ].map(([label, value]) => (
          <div key={label} className="border-t border-white/10 pt-3">
            <dt className="text-xs text-white/45">{label}</dt>
            <dd className="mt-1 font-mono text-2xl">{value}</dd>
          </div>
        ))}
      </dl>

      {narrative.finding ? (
        <section className="mt-12 max-w-xl">
          <h4 className="font-mono text-[11px] uppercase tracking-[0.2em] text-white/40">Finding</h4>
          <p className="mt-4 text-[24px] font-medium leading-[1.3] tracking-tight text-white">
            {narrative.finding}
          </p>
        </section>
      ) : null}

      <div className="mt-12 grid gap-10 sm:grid-cols-2">
        <SignalList title="Detected signals" items={narrative.detected} />
        <SignalList title="Weak signals" items={narrative.weak} />
      </div>

      <div className="mt-12 grid gap-10 sm:grid-cols-2">
        {[
          ["Red team", narrative.red],
          ["Blue team", narrative.blue],
        ].map(([title, body]) => (
          <section key={title} className="border-t border-white/10 pt-4">
            <h4 className="font-mono text-[11px] uppercase tracking-[0.2em] text-white/40">{title}</h4>
            <p className="mt-3 max-w-prose text-[16px] leading-7 text-white">{body}</p>
          </section>
        ))}
      </div>
    </article>
  );
}
