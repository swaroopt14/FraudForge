"use client";

import { useMemo, useState } from "react";
import type { GraphNode, GraphPayload } from "@/lib/api";
import { num } from "@/lib/format";

const RING: Record<string, number> = {
  customer: 0.28,
  device: 0.48,
  ip: 0.62,
  merchant: 0.78,
  beneficiary: 0.92,
  geo: 0.7,
  agent: 0.4,
};

const FILL: Record<string, string> = {
  customer: "#f5f5f5",
  device: "#ff5f00",
  ip: "#ff9a55",
  merchant: "#8a8a8a",
  beneficiary: "#ff5f00",
  geo: "#8a8a8a",
  agent: "#d0d0d0",
  transaction: "#ff5f00",
};

const TYPE_LABEL: Record<string, string> = {
  customer: "Account",
  device: "Device",
  ip: "IP",
  beneficiary: "Beneficiary",
  merchant: "Merchant",
  geo: "Location",
  agent: "Agent",
};

const LAYER_X: Record<string, number> = {
  ip: 90,
  device: 230,
  customer: 390,
  beneficiary: 560,
  merchant: 560,
  agent: 90,
};

type Mode = "focus" | "network" | "hubs" | "payee" | "device";
type Pane = "graph" | "path" | "network" | "signals";

function polar(cx: number, cy: number, r: number, t: number) {
  return { x: cx + r * Math.cos(t), y: cy + r * Math.sin(t) };
}

function layoutFocus(nodes: GraphNode[], family: string, width: number, height: number) {
  const pos = new Map<string, { x: number; y: number }>();
  const grouped = new Map<string, GraphNode[]>();
  for (const node of nodes) {
    const list = grouped.get(node.type) || [];
    list.push(node);
    grouped.set(node.type, list);
  }
  const hubType = family === "mule_network" ? "beneficiary" : family === "shared_device" ? "device" : family === "shared_ip" ? "ip" : "";
  if (hubType && (grouped.get(hubType) || []).length) {
    const cx = width / 2;
    const cy = height / 2;
    const hubs = grouped.get(hubType) || [];
    hubs.forEach((node, i) => {
      pos.set(node.id, polar(cx, cy, hubs.length === 1 ? 0 : 36, (Math.PI * 2 * i) / hubs.length));
    });
    const accounts = grouped.get("customer") || [];
    accounts.forEach((node, i) => {
      pos.set(node.id, polar(cx, cy, 150, (Math.PI * 2 * i) / Math.max(accounts.length, 1) - Math.PI / 2));
    });
    for (const [type, list] of grouped) {
      if (type === hubType || type === "customer") continue;
      list.forEach((node, i) => {
        pos.set(node.id, polar(cx, cy, 220, (Math.PI * 2 * i) / Math.max(list.length, 1) + 0.4));
      });
    }
    return pos;
  }
  for (const [type, list] of grouped) {
    const x = LAYER_X[type] ?? 390;
    list.forEach((node, i) => {
      const y = list.length === 1 ? height / 2 : 48 + ((height - 96) * i) / Math.max(list.length - 1, 1);
      pos.set(node.id, { x, y });
    });
  }
  return pos;
}

function layoutRing(nodes: GraphNode[], size: number) {
  const pos = new Map<string, { x: number; y: number }>();
  const grouped = new Map<string, GraphNode[]>();
  for (const node of nodes) {
    const list = grouped.get(node.type) || [];
    list.push(node);
    grouped.set(node.type, list);
  }
  const cx = size / 2;
  const cy = size / 2;
  for (const [type, list] of grouped) {
    const radius = (RING[type] ?? 0.7) * (size / 2 - 24);
    list.forEach((node, i) => {
      const t = (Math.PI * 2 * i) / Math.max(list.length, 1) - Math.PI / 2;
      pos.set(node.id, polar(cx, cy, radius, t));
    });
  }
  return pos;
}

export function AttackGraph({
  graph,
  events,
  title,
  subtitle,
}: {
  graph: GraphPayload;
  events?: GraphPayload["agent_events"];
  title?: string;
  subtitle?: string;
}) {
  const [pane, setPane] = useState<Pane>("graph");
  const [mode, setMode] = useState<Mode>("focus");
  const family = graph.family || "";
  const stats = graph.stats || {};
  const focus = graph.focus;
  const worldNodes = graph.nodes || [];
  const worldEdges = graph.edges || [];
  const hubs = new Set((graph.shared_hubs || []).map((h) => `${h.type}:${h.id}`));

  const view = useMemo(() => {
    if (pane === "network" || mode === "network") {
      return { nodes: worldNodes, edges: worldEdges, kind: "ring" as const };
    }
    if (mode === "hubs") {
      const hubNodes = worldNodes.filter((n) => hubs.has(n.id) || n.type === "customer");
      const keep = new Set(hubNodes.map((n) => n.id));
      return {
        nodes: hubNodes.slice(0, 60),
        edges: worldEdges.filter((e) => keep.has(e.source) && keep.has(e.target)).slice(0, 80),
        kind: "ring" as const,
      };
    }
    if (mode === "payee") {
      const edges = (focus?.edges || worldEdges).filter((e) => e.relation === "pays_beneficiary");
      const keep = new Set(edges.flatMap((e) => [e.source, e.target]));
      const nodes = (focus?.nodes || worldNodes).filter((n) => keep.has(n.id));
      return { nodes, edges, kind: "focus" as const };
    }
    if (mode === "device") {
      const edges = (focus?.edges || worldEdges).filter((e) => e.relation === "uses_device");
      const keep = new Set(edges.flatMap((e) => [e.source, e.target]));
      const nodes = (focus?.nodes || worldNodes).filter((n) => keep.has(n.id));
      return { nodes, edges, kind: "focus" as const };
    }
    return {
      nodes: focus?.nodes?.length ? focus.nodes : worldNodes.slice(0, 24),
      edges: focus?.edges?.length ? focus.edges : worldEdges.slice(0, 36),
      kind: "focus" as const,
    };
  }, [pane, mode, worldNodes, worldEdges, focus, hubs]);

  const size = view.kind === "ring" ? 520 : 640;
  const height = view.kind === "ring" ? 520 : 420;
  const pos =
    view.kind === "ring" ? layoutRing(view.nodes, size) : layoutFocus(view.nodes, family, size, height);

  return (
    <div className="mt-8 space-y-8">
      <div>
        <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-white/40">Attack graph</p>
        {title ? <h2 className="mt-2 text-2xl font-medium">{title}</h2> : null}
        {subtitle ? <p className="mt-1 font-mono text-xs text-white/40">{subtitle}</p> : null}
        <p className="mt-3 font-mono text-[11px] uppercase tracking-[0.16em] text-white/35">
          {num(stats.n_nodes ?? graph.n_nodes)} total nodes · {num(stats.n_edges ?? graph.n_edges)} relationships
        </p>
      </div>

      <dl className="grid grid-cols-2 gap-x-8 gap-y-4 sm:grid-cols-4">
        {[
          ["Attack nodes", num(focus?.n_nodes ?? view.nodes.length)],
          ["Attack edges", num(focus?.n_edges ?? view.edges.length)],
          ["Shared hubs", num(stats.shared_hubs ?? graph.attack_networks)],
          ["Compromised accts", num(stats.compromised_accounts)],
          ["New devices", num(stats.new_devices)],
          ["New beneficiaries", num(stats.new_beneficiaries)],
        ].map(([label, value]) => (
          <div key={label} className="border-t border-white/10 pt-3">
            <dt className="text-xs text-white/45">{label}</dt>
            <dd className="mt-1 font-mono text-xl">{value}</dd>
          </div>
        ))}
      </dl>

      <div className="flex flex-wrap gap-6 font-mono text-[11px] uppercase tracking-[0.18em] text-white/35">
        {(
          [
            ["graph", "Attack Graph"],
            ["path", "Attack Path"],
            ["network", "Network"],
            ["signals", "Signals"],
          ] as const
        ).map(([id, label]) => (
          <button key={id} type="button" className={pane === id ? "text-signal" : "hover:text-white"} onClick={() => setPane(id)}>
            {label}
          </button>
        ))}
      </div>

      {pane === "graph" || pane === "network" ? (
        <>
          {pane === "graph" ? (
            <fieldset className="font-mono text-[11px] uppercase tracking-[0.16em] text-white/40">
              Graph mode
              <div className="mt-3 flex flex-wrap gap-x-6 gap-y-2 normal-case tracking-normal text-sm text-white">
                {(
                  [
                    ["focus", "Attack Focus"],
                    ["network", "Full Network"],
                    ["hubs", "Shared Hubs"],
                    ["payee", "Account → Beneficiary"],
                    ["device", "Device → Account"],
                  ] as const
                ).map(([id, label]) => (
                  <label key={id} className="flex items-center gap-2">
                    <input type="radio" checked={mode === id} onChange={() => setMode(id)} />
                    {label}
                  </label>
                ))}
              </div>
            </fieldset>
          ) : null}
          <p className="max-w-xl text-sm text-white/50">
            {pane === "network" || mode === "network"
              ? "Full overlay: every entity in this run. Use Attack Focus to see the fraud motif."
              : "This is the attack, not the whole simulated world. Orange marks new or shared infrastructure."}
          </p>
          <ul className="flex flex-wrap gap-4 font-mono text-[11px] uppercase tracking-[0.14em] text-white/40">
            {Object.entries(TYPE_LABEL).map(([type, label]) => (
              <li key={type} className="flex items-center gap-2">
                <span className="inline-block h-2 w-2 rounded-full" style={{ background: FILL[type] }} />
                {label}
              </li>
            ))}
          </ul>
          {view.nodes.length === 0 ? (
            <p className="text-sm text-white/40">No graph for this run.</p>
          ) : (
            <svg
              viewBox={`0 0 ${size} ${height}`}
              className="h-[min(70vh,560px)] w-full"
              role="img"
              aria-label="Attack graph"
            >
              {view.edges.map((edge, i) => {
                const a = pos.get(edge.source);
                const b = pos.get(edge.target);
                if (!a || !b) return null;
                return (
                  <g key={`${edge.source}-${edge.target}-${i}`}>
                    <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="rgba(255,95,0,0.35)" strokeWidth={1.2} />
                    {view.kind === "focus" && edge.label ? (
                      <text
                        x={(a.x + b.x) / 2}
                        y={(a.y + b.y) / 2 - 6}
                        textAnchor="middle"
                        fill="rgba(255,255,255,0.35)"
                        fontSize="9"
                      >
                        {edge.label}
                      </text>
                    ) : null}
                  </g>
                );
              })}
              {view.nodes.map((node) => {
                const p = pos.get(node.id);
                if (!p) return null;
                const hub = hubs.has(node.id);
                const attack = node.flag === "new" || node.flag === "shared";
                return (
                  <g key={node.id}>
                    <circle
                      cx={p.x}
                      cy={p.y}
                      r={hub || attack ? 8 : 5}
                      fill={FILL[node.type] || "#f5f5f5"}
                      opacity={hub || attack ? 1 : 0.8}
                    />
                    {view.kind === "focus" ? (
                      <text x={p.x} y={p.y + 18} textAnchor="middle" fill="rgba(255,255,255,0.7)" fontSize="10">
                        {node.role || TYPE_LABEL[node.type] || node.type}
                      </text>
                    ) : null}
                    <title>
                      {node.role || node.type} {node.label}
                      {node.detected == null ? "" : node.detected ? " · detected" : " · missed"}
                    </title>
                  </g>
                );
              })}
            </svg>
          )}
        </>
      ) : null}

      {pane === "path" ? <AttackPath path={graph.path || []} /> : null}

      {pane === "signals" ? (
        <div className="grid gap-12 lg:grid-cols-2">
          <div>
            <h3 className="font-mono text-[11px] uppercase tracking-[0.2em] text-white/40">Blue Team result</h3>
            <ul className="mt-4 max-w-md">
              {(graph.blue || []).map((row) => (
                <li key={row.label} className="flex justify-between border-t border-white/10 py-2.5 text-sm">
                  <span>{row.label}</span>
                  <span className={row.status === "detected" ? "font-mono text-signal" : "font-mono text-white/45"}>
                    {row.status === "detected" ? "detected" : row.status === "missed" ? "missed" : "—"}
                  </span>
                </li>
              ))}
            </ul>
          </div>
          <div>
            <h3 className="font-mono text-[11px] uppercase tracking-[0.2em] text-white/40">Attack motif</h3>
            <ul className="mt-4 max-w-md">
              {(graph.motif || []).map((row) => (
                <li key={row.id} className="border-t border-white/10 py-2.5 text-sm">
                  <span className="mr-3 font-mono text-signal">{row.present ? "✓" : "–"}</span>
                  {row.label}
                </li>
              ))}
            </ul>
          </div>
        </div>
      ) : null}

      {(graph.shared_hubs || []).length && (pane === "graph" || pane === "network") ? (
        <ul className="space-y-2 font-mono text-xs text-white/55">
          {(graph.shared_hubs || []).slice(0, 6).map((hub) => (
            <li key={`${hub.type}:${hub.id}`}>
              <span className="text-signal">{hub.type}</span> {hub.id} · {hub.customers} accounts
            </li>
          ))}
        </ul>
      ) : null}
      {(events || graph.agent_events || []).length && pane === "signals" ? (
        <ul className="space-y-2 font-mono text-xs text-white/55">
          {(events || graph.agent_events || []).slice(0, 8).map((event) => (
            <li key={`${event.transaction_id}-${event.agent_id}-${event.reason}`}>
              {event.agent_id || event.intent} · {event.tool} · {event.reason}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function AttackPath({ path }: { path: GraphPayload["path"] }) {
  if (!path?.length) {
    return <p className="text-sm text-white/40">No attack path for this family yet.</p>;
  }
  return (
    <ol className="max-w-md">
      {path.map((step, i) => (
        <li key={`${step.id}-${i}`} className="border-t border-white/10 py-3">
          <p className="font-mono text-[11px] text-white/35">{String(i + 1).padStart(2, "0")}</p>
          <p className="mt-1 text-sm">{step.label}</p>
          <p className="mt-1 font-mono text-[11px] uppercase tracking-[0.14em] text-white/40">
            {step.status === "detected" ? "Blue detected" : step.status === "missed" ? "Blue missed" : step.type}
          </p>
        </li>
      ))}
    </ol>
  );
}
