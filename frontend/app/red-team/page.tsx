"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { AttackGraph } from "@/components/attack-graph";
import { ReportPane } from "@/components/report";
import { api, type GraphPayload, type LeaderboardRow, type RedTeamResult, type ThreatSummary } from "@/lib/api";
import { num, pct } from "@/lib/format";
import { behaviorRows } from "@/lib/signals";

const LEVELS = ["LOW", "MEDIUM", "HIGH", "ADAPTIVE"];
const SCALES = [1000, 10000, 100000];
const NETWORK_PRESETS = [
  { attack: "MUL-001", variant: "MUL-N01", label: "Mule Network" },
  { attack: "DEV-001", variant: "DEV-N01", label: "Shared Device" },
  { attack: "IP-001", variant: "IP-N01", label: "Shared IP" },
  { attack: "GEO-001", variant: "GEO-N01", label: "Impossible Travel" },
  { attack: "BEN-001", variant: "BEN-N02", label: "Beneficiary Coordination" },
  { attack: "MER-001", variant: "MER-V02", label: "Merchant Coordination" },
];

export default function RedTeamLabPage() {
  return (
    <Suspense fallback={<p className="font-mono text-sm text-white/40">Loading lab…</p>}>
      <RedTeamLab />
    </Suspense>
  );
}

function RedTeamLab() {
  const params = useSearchParams();
  const [threats, setThreats] = useState<ThreatSummary[]>([]);
  const [attackId, setAttackId] = useState(params.get("attack") || "BEN-001");
  const [variantId, setVariantId] = useState(params.get("variant") || "");
  const [difficulty, setDifficulty] = useState((params.get("difficulty") || "MEDIUM").toUpperCase());
  const [n, setN] = useState(Number(params.get("scale") || 1000));
  const [seed, setSeed] = useState(Number(params.get("seed") || 424242));
  const [population, setPopulation] = useState("normal_customers");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<RedTeamResult | null>(null);
  const [board, setBoard] = useState<LeaderboardRow[]>([]);
  const [tab, setTab] = useState<"result" | "missed" | "graph" | "report" | "board">("result");
  const [graph, setGraph] = useState<GraphPayload | null>(null);
  const [mode, setMode] = useState<"standard" | "network">("standard");

  const threat = threats.find((t) => t.attack_id === attackId);
  const variants = threat?.variants || [];

  useEffect(() => {
    void api<{ threats: ThreatSummary[] }>("/threats")
      .then((body) => {
        setThreats(body.threats);
        const wanted = params.get("attack") || attackId;
        if (body.threats.length && !body.threats.some((t) => t.attack_id === wanted)) {
          setAttackId(body.threats[0].attack_id);
        } else if (wanted) {
          setAttackId(wanted);
        }
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Threats unavailable"));
    void api<{ leaderboard: LeaderboardRow[] }>("/red-team/leaderboard")
      .then((body) => setBoard(body.leaderboard))
      .catch(() => undefined);
    const raw = sessionStorage.getItem("last_red_team");
    if (raw) {
      try {
        const saved = JSON.parse(raw) as RedTeamResult;
        setResult(saved);
        setGraph(saved.graph || null);
      } catch {
        /* ignore */
      }
    }
  }, []);

  useEffect(() => {
    if (variants.length && !variants.some((v) => v.id === variantId)) {
      setVariantId(variants[0].id);
    }
  }, [attackId, variants, variantId]);

  const simForReport = useMemo(() => {
    if (!result) return null;
    return {
      ...result,
      narrative: {
        finding: result.finding || "",
        detected: result.detection_signals || [],
        weak: [],
        red: "Replay this seed after Blue Team changes.",
        blue: "Add the listed bypass signals to the detector.",
      },
    };
  }, [result]);

  const detected = result ? result.detected ?? Math.max(0, result.generated - result.missed) : 0;
  const success = result ? 1 - (result.detection_rate || 0) : 0;
  const behavior = behaviorRows(result?.detection_signals || threat?.detection_signals);

  async function run() {
    setBusy(true);
    setError("");
    try {
      const body = await api<RedTeamResult>("/red-team/runs", {
        method: "POST",
        body: JSON.stringify({
          attack_id: attackId,
          variant_id: variantId || undefined,
          difficulty,
          scale: n,
          seed,
          target_population: population,
        }),
      });
      setResult(body);
      sessionStorage.setItem("last_red_team", JSON.stringify(body));
      sessionStorage.setItem("last_simulation", JSON.stringify(body));
      setGraph(body.graph || null);
      setTab("result");
      const lb = await api<{ leaderboard: LeaderboardRow[] }>("/red-team/leaderboard");
      setBoard(lb.leaderboard);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Run failed");
    } finally {
      setBusy(false);
    }
  }

  async function replay() {
    if (!result?.simulation_id) return;
    setBusy(true);
    setError("");
    try {
      const body = await api<RedTeamResult>(`/red-team/runs/${result.simulation_id}/replay`, { method: "POST" });
      setResult(body);
      sessionStorage.setItem("last_red_team", JSON.stringify(body));
      setGraph(body.graph || null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Replay failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rise grid gap-12 lg:grid-cols-[minmax(0,240px)_minmax(0,1fr)]">
      <div>
        <h1 className="text-3xl font-medium tracking-tight">Red Team Lab</h1>
        <p className="mt-2 text-sm text-white/55">
          Select a known threat, set difficulty and scale, then score it with the current Blue Team.
        </p>
        <div className="mt-6 flex gap-4 font-mono text-[11px] uppercase tracking-[0.16em]">
          <button type="button" className={mode === "standard" ? "text-signal" : "text-white/40"} onClick={() => setMode("standard")}>
            Standard
          </button>
          <button
            type="button"
            className={mode === "network" ? "text-signal" : "text-white/40"}
            onClick={() => {
              setMode("network");
              setAttackId("MUL-001");
              setVariantId("MUL-N01");
            }}
          >
            Network attack
          </button>
        </div>
        <form
          className="mt-8 space-y-5"
          onSubmit={(e) => {
            e.preventDefault();
            void run();
          }}
        >
          {mode === "network" ? (
            <label className="block text-xs uppercase tracking-[0.16em] text-white/40">
              Network attack
              <select
                className="mt-2 w-full border-b border-white/20 bg-transparent py-2 text-sm outline-none"
                value={`${attackId}:${variantId}`}
                onChange={(e) => {
                  const [nextAttack, nextVariant] = e.target.value.split(":");
                  setAttackId(nextAttack);
                  setVariantId(nextVariant);
                }}
              >
                {NETWORK_PRESETS.map((preset) => (
                  <option key={preset.variant} value={`${preset.attack}:${preset.variant}`} className="bg-ink">
                    {preset.label}
                  </option>
                ))}
              </select>
            </label>
          ) : (
            <label className="block text-xs uppercase tracking-[0.16em] text-white/40">
            Attack family
            <select
              className="mt-2 w-full border-b border-white/20 bg-transparent py-2 text-sm outline-none"
              value={attackId}
              onChange={(e) => setAttackId(e.target.value)}
            >
              {threats.map((t) => (
                <option key={t.attack_id} value={t.attack_id} className="bg-ink">
                  {t.attack_id} · {t.name}
                </option>
              ))}
            </select>
          </label>
          )}
          {mode === "standard" ? (
          <label className="block text-xs uppercase tracking-[0.16em] text-white/40">
            Variant
            <select
              className="mt-2 w-full border-b border-white/20 bg-transparent py-2 text-sm outline-none"
              value={variantId}
              onChange={(e) => setVariantId(e.target.value)}
            >
              {variants.map((v) => (
                <option key={v.id} value={v.id} className="bg-ink">
                  {v.id} · {v.name}
                </option>
              ))}
            </select>
          </label>
          ) : null}
          <label className="block text-xs uppercase tracking-[0.16em] text-white/40">
            Difficulty
            <select
              className="mt-2 w-full border-b border-white/20 bg-transparent py-2 text-sm outline-none"
              value={difficulty}
              onChange={(e) => setDifficulty(e.target.value)}
            >
              {LEVELS.map((level) => (
                <option key={level} value={level} className="bg-ink">
                  {level}
                </option>
              ))}
            </select>
          </label>
          {difficulty === "ADAPTIVE" ? (
            <p className="font-mono text-[11px] leading-5 text-white/40">
              Probe MEDIUM, then blend toward HIGH when the detector is already catching the family.
            </p>
          ) : null}
          <label className="block text-xs uppercase tracking-[0.16em] text-white/40">
            Population
            <input
              className="mt-2 w-full border-b border-white/20 bg-transparent py-2 font-mono text-sm outline-none"
              value={population}
              onChange={(e) => setPopulation(e.target.value)}
            />
          </label>
          <fieldset className="text-xs uppercase tracking-[0.16em] text-white/40">
            Scale
            <div className="mt-3 space-y-2 font-mono text-sm normal-case tracking-normal text-white">
              {SCALES.map((s) => (
                <label key={s} className="flex items-center gap-2">
                  <input type="radio" checked={n === s} onChange={() => setN(s)} />
                  {s.toLocaleString()}
                </label>
              ))}
            </div>
          </fieldset>
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
            {busy ? "Scoring…" : mode === "network" ? "Generate attack" : "Run attack"}
          </button>
          <button
            type="button"
            disabled={busy || !result}
            onClick={() => void replay()}
            className="w-full border-b border-white/20 py-3 text-sm text-white/70 disabled:opacity-30"
          >
            Replay
          </button>
        </form>
        {error ? <p className="mt-4 font-mono text-xs text-signal">{error}</p> : null}
      </div>

      <section>
        <div className="flex flex-wrap gap-6 font-mono text-[11px] uppercase tracking-[0.18em] text-white/35">
          {(["result", "missed", "graph", "report", "board"] as const).map((id) => (
            <button
              key={id}
              type="button"
              className={tab === id ? "text-signal" : "hover:text-white"}
              onClick={() => {
                setTab(id);
                if (id === "graph" && result?.simulation_id && !graph) {
                  void api<GraphPayload>(`/red-team/runs/${result.simulation_id}/graph`)
                    .then(setGraph)
                    .catch(() => undefined);
                }
              }}
            >
              {id === "board" ? "Leaderboard" : id === "missed" ? "Missed" : id === "graph" ? "Graph" : id === "report" ? "Report" : "Result"}
            </button>
          ))}
        </div>

        {tab === "result" ? (
          result ? (
            <div className="mt-8 space-y-10">
              <div>
                <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-white/40">Red Team run</p>
                <h2 className="mt-2 text-2xl font-medium">{result.attack_name || result.attack_family}</h2>
                <p className="mt-1 font-mono text-xs text-white/40">
                  {result.variant_id} · {result.difficulty} · {result.simulation_id}
                </p>
              </div>
              <dl className="grid grid-cols-2 gap-x-8 gap-y-6 sm:grid-cols-4">
                {[
                  ["Generated", num(result.generated)],
                  ["Detected", num(detected)],
                  ["Missed", num(result.missed)],
                  ["Detection", pct(result.detection_rate)],
                  ["Attack success", pct(success)],
                  ["Fidelity", pct(result.fidelity?.overall_fidelity)],
                  ["Precision", pct(result.metrics?.precision)],
                  ["PR-AUC", pct(result.metrics?.pr_auc)],
                ].map(([k, v]) => (
                  <div key={k} className="border-t border-white/10 pt-3">
                    <dt className="text-xs text-white/45">{k}</dt>
                    <dd className="mt-1 font-mono text-2xl">{v}</dd>
                  </div>
                ))}
              </dl>
              {result.entities ? (
                <dl className="grid grid-cols-2 gap-x-8 gap-y-4 sm:grid-cols-5 text-sm">
                  {[
                    ["Accounts", num(result.entities.customers)],
                    ["Devices", num(result.entities.devices)],
                    ["IPs", num(result.entities.ips)],
                    ["Beneficiaries", num(result.entities.beneficiaries)],
                    ["Network fidelity", pct(result.fidelity?.network_topology ?? result.fidelity?.network_fidelity)],
                  ].map(([k, v]) => (
                    <div key={k} className="border-t border-white/10 pt-3">
                      <dt className="text-xs text-white/45">{k}</dt>
                      <dd className="mt-1 font-mono">{v}</dd>
                    </div>
                  ))}
                </dl>
              ) : null}
              <div>
                <h3 className="font-mono text-[11px] uppercase tracking-[0.2em] text-white/40">Attack behavior</h3>
                <ul className="mt-4 max-w-xl space-y-2 text-sm">
                  {behavior.map((row) => (
                    <li key={row.id} className="grid grid-cols-[1fr_auto_1fr] items-center gap-3 border-t border-white/10 py-2">
                      <span className="text-white/50">{row.normal}</span>
                      <span className="text-white/25">→</span>
                      <span>{row.attack}</span>
                    </li>
                  ))}
                </ul>
              </div>
              <div className="flex flex-wrap gap-6 font-mono text-[11px] uppercase tracking-[0.16em]">
                <button type="button" className="text-signal" onClick={() => setTab("missed")}>
                  View missed
                </button>
                <button type="button" className="text-white/60 hover:text-white" onClick={() => setTab("graph")}>
                  View graph
                </button>
                {result.simulation_id ? (
                  <Link href={`/red-team/runs/${result.simulation_id}`} className="text-white/60 hover:text-white">
                    View report
                  </Link>
                ) : null}
                <button type="button" className="text-white/60 hover:text-white" onClick={() => void replay()}>
                  Replay
                </button>
              </div>
            </div>
          ) : (
            <p className="mt-8 max-w-sm text-[15px] text-white/40">No run yet. Configure a threat and run it.</p>
          )
        ) : null}

        {tab === "missed" ? (
          <table className="mt-8 w-full text-left text-sm">
            <thead className="font-mono text-[11px] uppercase tracking-[0.16em] text-white/35">
              <tr>
                <th className="pb-3 font-normal">Transaction</th>
                <th className="pb-3 font-normal">Attack</th>
                <th className="pb-3 font-normal">Risk</th>
                <th className="pb-3 font-normal">Decision</th>
              </tr>
            </thead>
            <tbody>
              {(result?.missed_transactions || []).map((row) => (
                <tr key={row.transaction_id} className="border-t border-white/10">
                  <td className="py-3 font-mono text-xs">
                    <Link href={`/explorer/${encodeURIComponent(row.transaction_id)}`} className="hover:text-signal">
                      {row.transaction_id}
                    </Link>
                  </td>
                  <td className="py-3 font-mono text-xs">{result?.attack_id}</td>
                  <td className="py-3 font-mono">{(row.fraud_probability * 100).toFixed(1)}%</td>
                  <td className="py-3">{row.decision}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : null}

        {tab === "graph" ? (
          graph || result?.graph ? (
            <AttackGraph
              graph={graph || result?.graph || { nodes: [], edges: [] }}
              events={result?.agent_events}
              title={result?.attack_name || result?.attack_family}
              subtitle={`${result?.attack_id || ""} · ${result?.variant_id || ""} · ${result?.difficulty || ""}`}
            />
          ) : (
            <p className="mt-8 max-w-sm text-[15px] text-white/40">Run an attack to draw its entity graph.</p>
          )
        ) : null}

        {tab === "report" && simForReport ? <ReportPane result={simForReport} /> : null}

        {tab === "board" ? (
          <table className="mt-8 w-full text-left text-sm">
            <thead className="font-mono text-[11px] uppercase tracking-[0.16em] text-white/35">
              <tr>
                <th className="pb-3 font-normal">Attack</th>
                <th className="pb-3 font-normal">Evasion</th>
                <th className="pb-3 font-normal">Detection</th>
                <th className="pb-3 font-normal">PR-AUC</th>
                <th className="pb-3 font-normal">Fidelity</th>
                <th className="pb-3 font-normal">Difficulty</th>
                <th className="pb-3 font-normal">Scale</th>
              </tr>
            </thead>
            <tbody>
              {board.map((row) => (
                <tr key={row.attack_id} className="border-t border-white/10">
                  <td className="py-3">{row.name}</td>
                  <td className="py-3 font-mono">{pct(row.evasion ?? row.attack_success)}</td>
                  <td className="py-3 font-mono">{pct(row.detection_rate)}</td>
                  <td className="py-3 font-mono">{pct(row.pr_auc)}</td>
                  <td className="py-3 font-mono">{pct(row.fidelity)}</td>
                  <td className="py-3">{row.difficulty}</td>
                  <td className="py-3 font-mono">{num(row.scale)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : null}
      </section>
    </div>
  );
}
