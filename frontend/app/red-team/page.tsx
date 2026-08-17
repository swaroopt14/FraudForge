"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ReportPane } from "@/components/report";
import { api, type AttackCatalogItem, type Simulation } from "@/lib/api";

const FALLBACK: AttackCatalogItem[] = [
  { id: "low_and_slow", name: "Low-and-slow", tier: "P0" },
  { id: "account_takeover", name: "Account takeover", tier: "P0" },
  { id: "velocity_attack", name: "Velocity attack", tier: "P0" },
  { id: "amount_anomaly", name: "Amount anomaly", tier: "P0" },
  { id: "beneficiary_anomaly", name: "Beneficiary anomaly", tier: "P0" },
  { id: "mule_network", name: "Mule network", tier: "P2" },
  { id: "shared_device", name: "Shared device", tier: "P2" },
  { id: "shared_ip", name: "Shared IP", tier: "P2" },
  { id: "geo_anomaly", name: "Geographic anomaly", tier: "P2" },
  { id: "combined_context", name: "Combined context", tier: "P2" },
];

function RedTeamInner() {
  const params = useSearchParams();
  const [attacks, setAttacks] = useState<AttackCatalogItem[]>(FALLBACK);
  const [attack, setAttack] = useState(params.get("attack") || "mule_network");
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
    api<{ attacks: AttackCatalogItem[] }>("/attacks")
      .then((body) => {
        if (body.attacks?.length) setAttacks(body.attacks);
      })
      .catch(() => {
        /* keep fallback */
      });
  }, []);

  useEffect(() => {
    const next = params.get("attack");
    if (next) setAttack(next);
  }, [params]);

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

  const p0 = attacks.filter((a) => a.tier !== "P2");
  const p2 = attacks.filter((a) => a.tier === "P2");
  const contextual = p2.some((a) => a.id === attack);

  return (
    <div className="rise grid gap-12 lg:grid-cols-[minmax(0,240px)_minmax(0,1fr)]">
      <div>
        <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-white/35">Red team</p>
        <h1 className="mt-2 text-4xl font-medium tracking-tight">Attack lab</h1>
        <p className="mt-2 text-sm text-white/55">
          Generate and stress-test. Blue Team observes the stream separately.
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
              <optgroup label="P0 — row-level" className="bg-ink">
                {p0.map((item) => (
                  <option key={item.id} value={item.id} className="bg-ink">
                    {item.name}
                  </option>
                ))}
              </optgroup>
              <optgroup label="P2 — contextual" className="bg-ink">
                {p2.map((item) => (
                  <option key={item.id} value={item.id} className="bg-ink">
                    {item.name}
                  </option>
                ))}
              </optgroup>
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
          <>
            <ReportPane key={result.simulation_id} result={result} />
            {contextual ? (
              <p className="mt-8 text-sm text-white/55">
                Stream ingested.{" "}
                <Link href="/blue-team" className="text-signal">
                  Open Blue Team defense
                </Link>
              </p>
            ) : null}
          </>
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

export default function RedTeam() {
  return (
    <Suspense fallback={<p className="font-mono text-sm text-white/40">Loading red team…</p>}>
      <RedTeamInner />
    </Suspense>
  );
}
