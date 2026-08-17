"use client";

import { useEffect, useState } from "react";
import { ReportPane } from "@/components/report";
import { api, type Simulation } from "@/lib/api";

const FAMILIES = [
  "low_and_slow",
  "account_takeover",
  "velocity_attack",
  "amount_anomaly",
  "beneficiary_anomaly",
];

export default function RedTeam() {
  const [attack, setAttack] = useState("low_and_slow");
  const [n, setN] = useState(1000);
  const [seed, setSeed] = useState(424242);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<Simulation | null>(null);

  useEffect(() => {
    const raw = sessionStorage.getItem("last_simulation");
    if (raw) {
      try {
        setResult(JSON.parse(raw) as Simulation);
      } catch {
        /* ignore */
      }
    }
  }, []);

  async function run() {
    setBusy(true);
    setError("");
    try {
      const body = await api<Simulation>("/simulation/generate", {
        method: "POST",
        body: JSON.stringify({
          attack_id: attack,
          transaction_count: n,
          seed,
          intensity: "medium",
        }),
      });
      setResult(body);
      sessionStorage.setItem("last_simulation", JSON.stringify(body));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Generate failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rise grid gap-12 lg:grid-cols-[minmax(0,240px)_minmax(0,1fr)]">
      <div>
        <h1 className="text-4xl font-medium tracking-tight">Red team</h1>
        <p className="mt-2 text-sm text-white/55">
          Generate a seeded family, score every row, write the adversarial report.
        </p>
        <form
          className="mt-8 space-y-5"
          onSubmit={(e) => {
            e.preventDefault();
            void run();
          }}
        >
          <label className="block text-xs uppercase tracking-[0.16em] text-white/40">
            Attack family
            <select
              className="mt-2 w-full border-b border-white/20 bg-transparent py-2 text-sm text-white outline-none"
              value={attack}
              onChange={(e) => setAttack(e.target.value)}
            >
              {FAMILIES.map((id) => (
                <option key={id} value={id} className="bg-ink">
                  {id.replaceAll("_", " ")}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-xs uppercase tracking-[0.16em] text-white/40">
            Transactions
            <input
              type="number"
              min={10}
              max={100000}
              className="mt-2 w-full border-b border-white/20 bg-transparent py-2 font-mono text-sm outline-none"
              value={n}
              onChange={(e) => setN(Number(e.target.value))}
            />
          </label>
          <label className="block text-xs uppercase tracking-[0.16em] text-white/40">
            Seed
            <input
              type="number"
              className="mt-2 w-full border-b border-white/20 bg-transparent py-2 font-mono text-sm outline-none"
              value={seed}
              onChange={(e) => setSeed(Number(e.target.value))}
            />
          </label>
          <button
            type="submit"
            disabled={busy}
            className="mt-4 w-full bg-signal py-3 text-sm font-medium text-ink transition-opacity hover:opacity-90 disabled:opacity-40"
          >
            {busy ? "Scoring…" : "Run red team test"}
          </button>
        </form>
        {error ? <p className="mt-4 font-mono text-xs text-signal">{error}</p> : null}
      </div>

      <section>
        <h2 className="font-mono text-[11px] uppercase tracking-[0.2em] text-white/40">Report</h2>
        {busy ? (
          <p className="mt-3 font-mono text-[11px] uppercase tracking-[0.18em] text-signal">Scoring…</p>
        ) : null}
        {result ? (
          <ReportPane key={result.simulation_id} result={result} />
        ) : busy ? null : (
          <div className="mt-6">
            <div className="h-0.5 w-10 bg-white/15" />
            <p className="mt-6 max-w-sm text-[15px] leading-6 text-white/40">
              No run yet. Generate a family to write the adversarial brief here.
            </p>
          </div>
        )}
      </section>
    </div>
  );
}
