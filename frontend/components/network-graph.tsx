"use client";

import type { NetworkEdge, NetworkNode } from "@/lib/api";

const TYPE_COLOR: Record<string, string> = {
  customer: "#f5f5f5",
  beneficiary: "#FF5F00",
  device: "#8a8a8a",
  ip: "#8a8a8a",
  merchant: "#555",
};

export function NetworkGraph({
  nodes,
  edges,
  focus,
  onSelect,
}: {
  nodes: NetworkNode[];
  edges: NetworkEdge[];
  focus?: string;
  onSelect: (id: string) => void;
}) {
  const shown = nodes.slice(0, 28);
  const ids = shown.map((n) => n.id);
  const pos = new Map<string, { x: number; y: number }>();
  const cx = 280;
  const cy = 170;
  shown.forEach((node, i) => {
    const a = (i / Math.max(shown.length, 1)) * Math.PI * 2 - Math.PI / 2;
    const r = node.type === "beneficiary" ? 40 : 120;
    pos.set(node.id, { x: cx + Math.cos(a) * r, y: cy + Math.sin(a) * (r * 0.72) });
  });
  if (focus && pos.has(focus)) pos.set(focus, { x: cx, y: cy });

  const visible = edges.filter((e) => ids.includes(e.source) && ids.includes(e.target)).slice(0, 80);

  return (
    <svg viewBox="0 0 560 340" className="h-[340px] w-full" role="img" aria-label="Payment network">
      {visible.map((edge, i) => {
        const a = pos.get(edge.source);
        const b = pos.get(edge.target);
        if (!a || !b) return null;
        return (
          <line
            key={`${edge.source}-${edge.relation}-${edge.target}-${i}`}
            x1={a.x}
            y1={a.y}
            x2={b.x}
            y2={b.y}
            stroke="rgba(255,255,255,0.16)"
            strokeWidth="1"
          />
        );
      })}
      {shown.map((node) => {
        const p = pos.get(node.id);
        if (!p) return null;
        const active = node.id === focus;
        return (
          <g key={node.id} className="cursor-pointer" onClick={() => onSelect(node.id)}>
            <circle
              cx={p.x}
              cy={p.y}
              r={active ? 7 : 4.5}
              fill={TYPE_COLOR[node.type] || "#f5f5f5"}
            />
            <text x={p.x + 9} y={p.y + 3} fill="rgba(255,255,255,0.55)" fontSize="9" fontFamily="ui-monospace, monospace">
              {node.type.slice(0, 3)} {node.id.slice(0, 10)}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
