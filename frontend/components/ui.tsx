export function Kpi({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="border-t border-white/10 pt-3">
      <p className="text-xs text-white/45">{label}</p>
      <p className="mt-1 font-mono text-2xl">{value}</p>
      {hint ? <p className="mt-1 font-mono text-[11px] text-white/30">{hint}</p> : null}
    </div>
  );
}

export function PageTitle({ title, children }: { title: string; children?: React.ReactNode }) {
  return (
    <div className="mb-10">
      <h1 className="text-3xl font-medium tracking-tight">{title}</h1>
      {children ? <p className="mt-2 max-w-xl text-sm text-white/50">{children}</p> : null}
    </div>
  );
}

export function Section({ title, children }: { title: string; children?: React.ReactNode }) {
  return (
    <section>
      <h2 className="font-mono text-[11px] uppercase tracking-[0.2em] text-white/40">{title}</h2>
      {children}
    </section>
  );
}

export function Meter({ label, value }: { label: string; value?: number }) {
  const v = value == null || Number.isNaN(value) ? 0 : Math.max(0, Math.min(1, value));
  const shown = value == null || Number.isNaN(value) ? "—" : `${(value * 100).toFixed(1)}%`;
  return (
    <div className="grid grid-cols-[9rem_1fr_3.75rem] items-center gap-3">
      <span className="text-sm text-white/55">{label}</span>
      <div className="h-1.5 bg-white/10">
        <div className="h-1.5 bg-signal" style={{ width: `${v * 100}%` }} />
      </div>
      <span className="text-right font-mono text-sm">{shown}</span>
    </div>
  );
}

export const th = "pb-3 font-normal";
export const td = "py-3";

