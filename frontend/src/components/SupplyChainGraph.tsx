"use client";

import { useMemo, useState } from "react";

/**
 * SupplyChainGraph — a real node-and-edge visualisation of a sector's supply
 * chain. Companies are laid out in columns by chain layer (upstream → down-
 * stream) and the `flows` are drawn as directed curves between them, so the
 * second-order relationships are *visible* rather than implied by "in/out"
 * counts.
 *
 * Interactions:
 *  - Click a company node → selects it (drives the detail panel on the page).
 *  - Hover a node → focuses its supply chain (its links + neighbours light up,
 *    everything else dims), which is the "wow" moment for the differentiator.
 *
 * Layout is computed deterministically (no DOM measurement) and rendered in a
 * single SVG with a viewBox, so it scales cleanly and never mis-aligns edges.
 */

export interface GraphNode {
  id: string;
  name: string;
  /** false = an external raw-material / IP input with no tracked ticker. */
  hasCompany: boolean;
}

export interface GraphLayer {
  name: string;
  color: string;
  nodes: GraphNode[];
}

export interface GraphFlow {
  from: string;
  to: string;
  label?: string;
  value: number;
}

// ── Layout constants (SVG user units) ──────────────────────────────
const NODE_W = 132;
const NODE_H = 48;
const COL_GAP = 40;
const ROW_GAP = 22;
const ROW_H = NODE_H + ROW_GAP;
const PAD_X = 22;
const PAD_TOP = 40; // room for the layer label row
const PAD_BOTTOM = 22;

interface Placed {
  id: string;
  name: string;
  hasCompany: boolean;
  x: number;
  y: number;
  cx: number;
  cy: number;
  inX: number;
  outX: number;
  layerName: string;
}

function truncate(text: string, max = 18): string {
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}

export function SupplyChainGraph({
  layers,
  flows,
  activeTicker,
  onSelect,
}: {
  layers: GraphLayer[];
  flows: GraphFlow[];
  activeTicker: string | null;
  onSelect: (ticker: string) => void;
}) {
  const [hovered, setHovered] = useState<string | null>(null);
  // Gold highlight follows the selected company (persistent) or the hovered one.
  const edgeFocus = hovered ?? activeTicker;
  // Dimming only kicks in while hovering, so the default view shows the whole map.
  const dimFocus = hovered;

  const { placed, width, height, layerLabels } = useMemo(() => {
    const columns = layers.length;
    const maxRows = Math.max(1, ...layers.map((l) => l.nodes.length));
    const w = PAD_X * 2 + columns * NODE_W + Math.max(0, columns - 1) * COL_GAP;
    const h = PAD_TOP + maxRows * NODE_H + Math.max(0, maxRows - 1) * ROW_GAP + PAD_BOTTOM;

    const map = new Map<string, Placed>();
    const labels: { name: string; color: string; x: number }[] = [];

    layers.forEach((layer, i) => {
      const colLeftX = PAD_X + i * (NODE_W + COL_GAP);
      labels.push({ name: layer.name, color: layer.color, x: colLeftX });
      const startY = PAD_TOP + ((maxRows - layer.nodes.length) / 2) * ROW_H;
      layer.nodes.forEach((node, j) => {
        const y = startY + j * ROW_H;
        map.set(node.id, {
          id: node.id,
          name: node.name,
          hasCompany: node.hasCompany,
          x: colLeftX,
          y,
          cx: colLeftX + NODE_W / 2,
          cy: y + NODE_H / 2,
          inX: colLeftX,
          outX: colLeftX + NODE_W,
          layerName: layer.name,
        });
      });
    });

    return { placed: map, width: w, height: h, layerLabels: labels };
  }, [layers]);

  // Tickers directly connected to the focused node (for the highlight effect).
  const connected = useMemo(() => {
    if (!dimFocus) return null;
    const set = new Set<string>([dimFocus]);
    for (const f of flows) {
      if (f.from === dimFocus) set.add(f.to);
      if (f.to === dimFocus) set.add(f.from);
    }
    return set;
  }, [dimFocus, flows]);

  const drawnFlows = flows.filter((f) => placed.has(f.from) && placed.has(f.to));

  return (
    <div className="overflow-x-auto pb-1">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        width="100%"
        role="img"
        aria-label="Supply chain relationship graph"
        style={{ minWidth: Math.min(width, 900), color: "var(--al-on-surface)", display: "block" }}
      >
        <defs>
          <marker id="sc-arrow" markerWidth="7" markerHeight="7" refX="6" refY="3.2" orient="auto">
            <path d="M0,0 L7,3.2 L0,6.4 Z" fill="var(--al-on-surface-muted)" opacity="0.55" />
          </marker>
          <marker id="sc-arrow-hot" markerWidth="8" markerHeight="8" refX="6.5" refY="3.6" orient="auto">
            <path d="M0,0 L8,3.6 L0,7.2 Z" fill="var(--al-gold)" />
          </marker>
        </defs>

        {/* Layer labels + column tint */}
        {layerLabels.map((label) => (
          <g key={label.name}>
            <rect x={label.x} y={14} width={22} height={5} rx={2.5} fill={label.color} />
            <text
              x={label.x}
              y={32}
              fontSize={10.5}
              fontWeight={700}
              letterSpacing={0.4}
              fill="var(--al-on-surface-muted)"
              style={{ textTransform: "uppercase" }}
            >
              {truncate(label.name, 16)}
            </text>
          </g>
        ))}

        {/* Edges */}
        {drawnFlows.map((f, idx) => {
          const a = placed.get(f.from)!;
          const b = placed.get(f.to)!;
          const x1 = a.outX;
          const y1 = a.cy;
          const x2 = b.inX;
          const y2 = b.cy;
          const dx = Math.max(34, Math.abs(x2 - x1) * 0.45);
          const path = `M ${x1} ${y1} C ${x1 + dx} ${y1}, ${x2 - dx} ${y2}, ${x2} ${y2}`;
          const hot = edgeFocus != null && (f.from === edgeFocus || f.to === edgeFocus);
          const dim = dimFocus != null && !(f.from === dimFocus || f.to === dimFocus);
          return (
            <path
              key={`${f.from}-${f.to}-${idx}`}
              d={path}
              fill="none"
              stroke={hot ? "var(--al-gold)" : "var(--al-on-surface-muted)"}
              strokeWidth={hot ? 2.4 : 1.3}
              strokeOpacity={dim ? 0.12 : hot ? 0.95 : 0.4}
              markerEnd={hot ? "url(#sc-arrow-hot)" : "url(#sc-arrow)"}
            />
          );
        })}

        {/* Nodes */}
        {Array.from(placed.values()).map((n) => {
          const isActive = n.id === activeTicker;
          const inFocus = !connected || connected.has(n.id);
          const dim = !inFocus;
          const stroke = isActive
            ? "var(--al-gold)"
            : n.hasCompany
              ? "var(--al-outline)"
              : "var(--al-outline)";
          return (
            <g
              key={n.id}
              transform={`translate(${n.x} ${n.y})`}
              style={{ cursor: n.hasCompany ? "pointer" : "default", opacity: dim ? 0.28 : 1, transition: "opacity 120ms" }}
              onClick={n.hasCompany ? () => onSelect(n.id) : undefined}
              onMouseEnter={() => setHovered(n.id)}
              onMouseLeave={() => setHovered(null)}
            >
              <rect
                width={NODE_W}
                height={NODE_H}
                rx={11}
                fill={isActive ? "var(--al-gold-soft, rgba(200,169,81,0.12))" : "var(--al-surface, rgba(148,163,184,0.06))"}
                stroke={stroke}
                strokeWidth={isActive ? 2 : 1}
                strokeDasharray={n.hasCompany ? undefined : "4 3"}
              />
              <text x={11} y={20} fontSize={13} fontWeight={800} fill="currentColor" style={{ fontFamily: "var(--font-mono, monospace)" }}>
                {truncate(n.id, 12)}
              </text>
              <text x={11} y={36} fontSize={9.5} fill="var(--al-on-surface-muted)">
                {truncate(n.hasCompany ? n.name : "External input", 17)}
              </text>
            </g>
          );
        })}
      </svg>

      <p className="mt-2 px-1 text-xs leading-5" style={{ color: "var(--al-on-surface-muted)" }}>
        Each arrow is a mapped supply relationship (supplier → customer). Hover or select a company to
        trace its chain — <span style={{ color: "var(--al-gold)" }}>gold</span> links are the ripple paths a
        catalyst would travel through.
      </p>
    </div>
  );
}
