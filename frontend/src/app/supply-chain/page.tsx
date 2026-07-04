"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Activity, ArrowRight, Factory, LinkIcon, Network, PackageOpen, Workflow } from "lucide-react";

import {
  fetchSupplyChain,
  fetchSupplyChainSectors,
  type SupplyChainCompany,
  type SupplyChainData,
  type SupplyChainFlow,
} from "@/lib/api";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState, EmptyState } from "@/components/StateMessage";
import { MetricChip, Pill } from "@/components/primitives";
import { cn } from "@/lib/utils";
import { useMarket, MARKET_LABELS } from "@/lib/market-context";

const NODE_COLORS = ["#5C9CE6", "#81C784", "#FFB74D", "#CE93D8", "#F06292", "#94a3b8"];
const SEGMENT_COLORS = ["#5C9CE6", "#C8A951", "#81C784", "#F06292", "#CE93D8", "#FFB74D"];

interface FlowMapNode {
  id: string;
  layerName: string;
  company?: SupplyChainCompany;
  incoming: number;
  outgoing: number;
}

interface FlowMapLayer {
  name: string;
  color: string;
  nodes: FlowMapNode[];
}

function buildFlowMap(data: SupplyChainData): { layers: FlowMapLayer[]; topFlows: SupplyChainFlow[] } {
  const companies = new Map(data.companies.map((company) => [company.ticker, company] as const));
  const layerMeta = data.chain_layers.map((layer, index) => ({
    name: layer.name,
    color: layer.color ?? NODE_COLORS[index % NODE_COLORS.length],
  }));
  const layerNames = layerMeta.map((layer) => layer.name);
  const demandLayerName = "End demand";

  function ensureDemandLayer() {
    if (!layerNames.includes(demandLayerName)) {
      layerNames.push(demandLayerName);
      layerMeta.push({ name: demandLayerName, color: "#64748b" });
    }
  }

  function layerIndex(name: string | null | undefined): number | null {
    if (!name) return null;
    const index = layerNames.indexOf(name);
    return index >= 0 ? index : null;
  }

  function inferLayerName(name: string): string {
    const company = companies.get(name);
    const companyLayerIndex = layerIndex(company?.layer);
    if (companyLayerIndex != null) return layerNames[companyLayerIndex];

    const outgoingTarget = data.key_flows
      .map((flow) => (flow.from === name ? companies.get(flow.to) : undefined))
      .find((item): item is SupplyChainCompany => Boolean(item?.layer));
    const outgoingIndex = layerIndex(outgoingTarget?.layer);
    if (outgoingIndex != null) return layerNames[Math.max(0, outgoingIndex - 1)];

    const incomingSource = data.key_flows
      .map((flow) => (flow.to === name ? companies.get(flow.from) : undefined))
      .find((item): item is SupplyChainCompany => Boolean(item?.layer));
    const incomingIndex = layerIndex(incomingSource?.layer);
    if (incomingIndex != null) {
      const nextIndex = incomingIndex + 1;
      if (nextIndex < layerNames.length) return layerNames[nextIndex];
      ensureDemandLayer();
      return demandLayerName;
    }

    return layerNames[0] ?? "Supply inputs";
  }

  const nodeNames = new Set<string>();
  for (const company of data.companies) nodeNames.add(company.ticker);
  for (const flow of data.key_flows) {
    nodeNames.add(flow.from);
    nodeNames.add(flow.to);
  }

  const nodes = Array.from(nodeNames).map((name) => ({
    id: name,
    layerName: inferLayerName(name),
    company: companies.get(name),
    incoming: data.key_flows.filter((flow) => flow.to === name).length,
    outgoing: data.key_flows.filter((flow) => flow.from === name).length,
  }));

  const layers = layerMeta.map((layer) => ({
    ...layer,
    nodes: nodes
      .filter((node) => node.layerName === layer.name)
      .sort((a, b) => Number(Boolean(b.company)) - Number(Boolean(a.company)) || (b.incoming + b.outgoing) - (a.incoming + a.outgoing) || a.id.localeCompare(b.id)),
  }));

  return {
    layers,
    topFlows: [...data.key_flows].sort((a, b) => b.value - a.value).slice(0, 8),
  };
}

function firstCompany(chain: SupplyChainData | undefined): string | null {
  return chain?.companies[0]?.ticker ?? null;
}

function SegmentBars({
  title,
  subtitle,
  data,
  tone,
}: {
  title: string;
  subtitle: string;
  data: Record<string, { pct: number; description?: string; source?: string }>;
  tone: "revenue" | "cost";
}) {
  const rows = Object.entries(data).sort((a, b) => b[1].pct - a[1].pct);

  return (
    <section className="al-glass p-5 space-y-4">
      <div>
        <div className="al-eyebrow">{tone === "revenue" ? "Revenue breakdown" : "Cost structure"}</div>
        <h2 className="mt-1 text-lg">{title}</h2>
        <p className="mt-1 text-sm" style={{ color: "var(--al-on-surface-muted)" }}>{subtitle}</p>
      </div>
      <div className="space-y-3">
        {rows.length ? rows.map(([label, item], index) => (
          <div key={label} className="space-y-1.5">
            <div className="flex items-center justify-between gap-3 text-sm">
              <span className="truncate font-medium">{label}</span>
              <span className="font-mono tabular-nums" style={{ color: "var(--al-on-surface-muted)" }}>{item.pct}%</span>
            </div>
            <div className="bar-track h-2.5">
              <div
                className={cn("bar-fill", tone === "cost" && "bar-bearish")}
                style={{
                  width: `${Math.min(100, Math.max(4, item.pct))}%`,
                  background: tone === "revenue" ? SEGMENT_COLORS[index % SEGMENT_COLORS.length] : undefined,
                }}
              />
            </div>
            {(item.description ?? item.source) ? (
              <p className="text-xs leading-5" style={{ color: "var(--al-on-surface-muted)" }}>
                {item.description ?? item.source}
              </p>
            ) : null}
          </div>
        )) : (
          <p className="text-sm" style={{ color: "var(--al-on-surface-muted)" }}>No segment data available.</p>
        )}
      </div>
    </section>
  );
}

function CompanyAtGlance({ company, chain }: { company: SupplyChainCompany; chain: SupplyChainData }) {
  return (
    <section className="al-glass p-5 space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="al-eyebrow">Company at a glance</div>
          <h2 className="mt-1 text-xl">{company.ticker} - {company.name}</h2>
          {company.layer ? <p className="mt-1 text-sm" style={{ color: "var(--al-on-surface-muted)" }}>{company.layer}</p> : null}
        </div>
        <div className="flex flex-wrap gap-2">
          <MetricChip label="Upstream" value={company.receives_from.length} />
          <MetricChip label="Downstream" value={company.supplies_to.length} />
          <MetricChip label="Products" value={company.products.length} />
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <div>
          <div className="mb-2 flex items-center gap-2 text-sm font-semibold">
            <PackageOpen className="size-4" aria-hidden style={{ color: "var(--al-gold)" }} /> Products
          </div>
          <div className="flex flex-wrap gap-2">
            {company.products.length ? company.products.map((product) => <Pill key={product} variant="gray">{product}</Pill>) : <span className="text-sm" style={{ color: "var(--al-on-surface-muted)" }}>No product data.</span>}
          </div>
        </div>
        <div>
          <div className="mb-2 flex items-center gap-2 text-sm font-semibold">
            <Factory className="size-4" aria-hidden style={{ color: "var(--al-gold)" }} /> Receives from
          </div>
          <div className="flex flex-wrap gap-2">
            {company.receives_from.length ? company.receives_from.map((ticker) => <Pill key={ticker} variant="gold">{ticker}</Pill>) : <span className="text-sm" style={{ color: "var(--al-on-surface-muted)" }}>No upstream links.</span>}
          </div>
        </div>
        <div>
          <div className="mb-2 flex items-center gap-2 text-sm font-semibold">
            <LinkIcon className="size-4" aria-hidden style={{ color: "var(--al-gold)" }} /> Supplies to
          </div>
          <div className="flex flex-wrap gap-2">
            {company.supplies_to.length ? company.supplies_to.map((ticker) => <Pill key={ticker} variant="green">{ticker}</Pill>) : <span className="text-sm" style={{ color: "var(--al-on-surface-muted)" }}>No downstream links.</span>}
          </div>
        </div>
      </div>

      <div className="rounded-xl border p-4 text-sm leading-6" style={{ borderColor: "var(--al-outline)", color: "var(--al-on-surface-muted)" }}>
        {company.ticker} sits inside {chain.name}. Use this view to understand whether a catalyst is upstream input pressure, downstream demand, or company-specific execution.
      </div>
    </section>
  );
}

function SectorComparison({ chain }: { chain: SupplyChainData }) {
  const rows = chain.companies.map((company) => {
    const top = Object.entries(company.revenue_segments).sort((a, b) => b[1].pct - a[1].pct)[0];
    return { company, topLabel: top?.[0] ?? "No revenue segment", pct: top?.[1].pct ?? 0 };
  });

  return (
    <section className="al-glass p-5 space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="al-eyebrow">Sector revenue comparison</div>
          <h2 className="mt-1 text-lg">Dominant revenue stream by company</h2>
        </div>
        <Pill variant="gray">{chain.companies.length} companies</Pill>
      </div>
      <div className="space-y-3">
        {rows.map(({ company, topLabel, pct }) => (
          <div key={company.ticker} className="grid gap-2 sm:grid-cols-[90px_1fr_56px] sm:items-center">
            <div className="font-mono text-sm font-bold">{company.ticker}</div>
            <div>
              <div className="flex items-center justify-between gap-3 text-xs" style={{ color: "var(--al-on-surface-muted)" }}>
                <span className="truncate">{topLabel}</span>
              </div>
              <div className="bar-track mt-1 h-2.5">
                <div className="bar-fill" style={{ width: `${Math.min(100, Math.max(4, pct))}%` }} />
              </div>
            </div>
            <div className="text-right font-mono text-sm tabular-nums">{pct}%</div>
          </div>
        ))}
      </div>
    </section>
  );
}

function NewsPulsePlaceholder({ chain }: { chain: SupplyChainData }) {
  return (
    <section className="al-glass p-5 space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="al-eyebrow">Research overlay</div>
          <h2 className="mt-1 text-lg">Curated topology scope</h2>
        </div>
        <Pill variant="gray">static map</Pill>
      </div>
      <div className="flex flex-wrap items-center justify-center gap-3 py-4">
        {chain.companies.slice(0, 12).map((company, index) => {
          return (
            <div
              key={company.ticker}
              className="flex size-16 items-center justify-center rounded-full border text-center font-mono text-sm font-bold"
              style={{
                borderColor: "var(--al-outline)",
                background: index % 2 ? "rgba(92,156,230,0.10)" : "rgba(200,169,81,0.10)",
              }}
            >
              {company.ticker}
            </div>
          );
        })}
      </div>
      <p className="text-sm leading-6" style={{ color: "var(--al-on-surface-muted)" }}>
        These are the names in the curated map — sized equally, since the bubbles show membership, not weight. The map is built from known relationships and public disclosures. Use signal-card evidence to decide whether a new catalyst is actually moving through these suppliers, customers, or cost inputs.
      </p>
    </section>
  );
}

function SupplyChainMap({
  chain,
  activeTicker,
  onSelectCompany,
}: {
  chain: SupplyChainData;
  activeTicker: string | null;
  onSelectCompany: (ticker: string) => void;
}) {
  const flowMap = useMemo(() => buildFlowMap(chain), [chain]);

  return (
    <section className="al-glass p-5 space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="al-eyebrow">Supply chain flow</div>
          <h2 className="mt-1 text-xl">{chain.name}</h2>
          <p className="mt-1 max-w-3xl text-sm" style={{ color: "var(--al-on-surface-muted)" }}>{chain.description}</p>
        </div>
        <Workflow className="size-6" aria-hidden style={{ color: "var(--al-gold)" }} />
      </div>

      <div className="overflow-x-auto pb-2">
        <div
          className="grid min-w-[760px] gap-3 lg:min-w-[980px]"
          style={{ gridTemplateColumns: `repeat(${flowMap.layers.length}, minmax(150px, 1fr))` }}
        >
          {flowMap.layers.map((layer, index) => (
            <div key={layer.name} className="rounded-xl border bg-background/45 p-3" style={{ borderColor: "var(--al-outline)" }}>
              <div className="flex min-h-10 items-center justify-between gap-2">
                <div className="min-w-0">
                  <div className="h-1.5 w-10 rounded-full" style={{ background: layer.color }} />
                  <div className="mt-2 text-xs font-semibold uppercase leading-4 tracking-wide">{layer.name}</div>
                </div>
                {index < flowMap.layers.length - 1 ? <ArrowRight className="size-4 shrink-0" aria-hidden style={{ color: "var(--al-on-surface-muted)" }} /> : null}
              </div>

              <div className="mt-4 space-y-2">
                {layer.nodes.length ? layer.nodes.map((node) => {
                  const isActive = node.id === activeTicker;
                  const content = (
                    <>
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <div className="truncate font-mono text-sm font-bold">{node.id}</div>
                          <div className="mt-0.5 truncate text-xs" style={{ color: "var(--al-on-surface-muted)" }}>
                            {node.company?.name ?? "External input"}
                          </div>
                        </div>
                        {node.company ? <Pill variant={isActive ? "gold" : "gray"}>{isActive ? "active" : "company"}</Pill> : null}
                      </div>
                      <div className="mt-3 grid grid-cols-2 gap-2 text-[11px] tabular-nums" style={{ color: "var(--al-on-surface-muted)" }}>
                        <span>{node.incoming} in</span>
                        <span className="text-right">{node.outgoing} out</span>
                      </div>
                    </>
                  );

                  if (node.company) {
                    return (
                      <button
                        key={node.id}
                        type="button"
                        onClick={() => onSelectCompany(node.id)}
                        className={cn("w-full rounded-lg border p-3 text-left transition hover:-translate-y-0.5", isActive && "shadow-sm")}
                        style={{
                          borderColor: isActive ? "var(--al-gold)" : "var(--al-outline)",
                          background: isActive ? "rgba(200,169,81,0.10)" : "transparent",
                        }}
                      >
                        {content}
                      </button>
                    );
                  }

                  return (
                    <div key={node.id} className="rounded-lg border border-dashed p-3" style={{ borderColor: "var(--al-outline)" }}>
                      {content}
                    </div>
                  );
                }) : (
                  <div className="rounded-lg border border-dashed p-3 text-xs" style={{ borderColor: "var(--al-outline)", color: "var(--al-on-surface-muted)" }}>
                    No mapped nodes.
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-4">
        {flowMap.topFlows.map((flow) => (
          <div key={`${flow.from}-${flow.to}-${flow.label}`} className="rounded-xl border p-3" style={{ borderColor: "var(--al-outline)" }}>
            <div className="flex items-center gap-2 text-xs font-semibold">
              <span className="font-mono">{flow.from}</span>
              <ArrowRight className="size-3" aria-hidden style={{ color: "var(--al-gold)" }} />
              <span className="font-mono">{flow.to}</span>
            </div>
            <div className="mt-2 text-xs leading-5" style={{ color: "var(--al-on-surface-muted)" }}>
              {flow.label ?? "Mapped dependency"} · weight {flow.value}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

export default function SupplyChainPage() {
  const { market } = useMarket();
  const { data: sectors } = useQuery({
    queryKey: ["supply-chain", "sectors", market],
    queryFn: () => fetchSupplyChainSectors(market),
    staleTime: 5 * 60 * 1000,
  });

  const [selected, setSelected] = useState<string | null>(null);
  // Only honour the manual selection when it still belongs to the active market.
  const selectedInMarket = selected && (sectors ?? []).some((s) => s.id === selected);
  const sectorId = (selectedInMarket ? selected : null) ?? sectors?.[0]?.id ?? null;

  const { data: chain, isLoading, isError, refetch } = useQuery({
    queryKey: ["supply-chain", sectorId],
    queryFn: () => fetchSupplyChain(sectorId!),
    enabled: !!sectorId,
  });

  const [selectedCompany, setSelectedCompany] = useState<string | null>(null);
  const activeTicker = selectedCompany ?? firstCompany(chain);
  const activeCompany = chain?.companies.find((company) => company.ticker === activeTicker) ?? chain?.companies[0] ?? null;

  const hasSectors = (sectors?.length ?? 0) > 0;

  return (
    <div className="space-y-5">
      <header className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <div className="al-eyebrow">Supply Chain Intelligence</div>
          <h1 className="mt-1 text-2xl sm:text-3xl md:text-4xl">Market structure, not just tickers</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6" style={{ color: "var(--al-on-surface-muted)" }}>
            Curated topology from public disclosures: revenue streams, cost inputs, company relationships, and sector flow.
          </p>
        </div>
        {hasSectors ? (
          <label className="flex w-full flex-col gap-1 text-sm md:w-auto md:min-w-60">
            <span className="al-eyebrow">Sector · {MARKET_LABELS[market].short}</span>
            <select
              className="rounded-xl border bg-background px-3 py-2 text-sm"
              style={{ borderColor: "var(--al-outline)" }}
              value={sectorId ?? ""}
              onChange={(event) => {
                setSelected(event.target.value);
                setSelectedCompany(null);
              }}
              disabled={!sectors}
            >
              {(sectors ?? []).map((sector) => (
                <option key={sector.id} value={sector.id}>{sector.name}</option>
              ))}
            </select>
          </label>
        ) : null}
      </header>

      {!hasSectors && sectors ? (
        <EmptyState
          title={`No ${MARKET_LABELS[market].name} supply-chain coverage yet`}
          detail={`Curated supply-chain topology currently covers ${MARKET_LABELS.us.name} sectors only (AI & Semiconductors, Space & Rocket, Optical). Switch the market toggle back to ${MARKET_LABELS.us.short} to explore them.`}
        />
      ) : null}

      {hasSectors && isLoading ? <Skeleton className="h-96 w-full rounded-2xl" /> : null}
      {hasSectors && isError ? <ErrorState title="Failed to load supply chain" onRetry={() => refetch()} /> : null}

      {hasSectors && chain ? (
        <>
          <section className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <MetricChip label="Companies" value={chain.companies.length} className="min-w-0" />
            <MetricChip label="Flows" value={chain.key_flows.length} className="min-w-0" />
            <MetricChip label="Layers" value={chain.chain_layers.length} className="min-w-0" />
            <MetricChip label="Selected" value={activeCompany?.ticker ?? "-"} className="min-w-0" />
          </section>

          {chain.key_flows.length ? (
            <SupplyChainMap chain={chain} activeTicker={activeCompany?.ticker ?? null} onSelectCompany={setSelectedCompany} />
          ) : null}

          <NewsPulsePlaceholder chain={chain} />

          <section className="al-glass p-5 space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="al-eyebrow">Company deep dive</div>
                <h2 className="mt-1 text-lg">Revenue, costs, and relationships</h2>
              </div>
              <Network className="size-5" aria-hidden style={{ color: "var(--al-gold)" }} />
            </div>
            <div className="flex gap-2 overflow-x-auto pb-1">
              {chain.companies.map((company) => (
                <button
                  key={company.ticker}
                  type="button"
                  onClick={() => setSelectedCompany(company.ticker)}
                  className={cn("min-w-[160px] rounded-xl border px-3 py-2 text-left transition", activeCompany?.ticker === company.ticker && "shadow-sm")}
                  style={{
                    borderColor: activeCompany?.ticker === company.ticker ? "var(--al-gold)" : "var(--al-outline)",
                    background: activeCompany?.ticker === company.ticker ? "rgba(200,169,81,0.10)" : "transparent",
                  }}
                >
                  <div className="font-mono text-sm font-bold">{company.ticker}</div>
                  <div className="truncate text-xs" style={{ color: "var(--al-on-surface-muted)" }}>{company.name}</div>
                </button>
              ))}
            </div>
          </section>

          {activeCompany ? (
            <>
              <section className="grid gap-5 lg:grid-cols-2">
                <SegmentBars
                  title={`${activeCompany.ticker} revenue`}
                  subtitle={`How ${activeCompany.name} earns money`}
                  data={activeCompany.revenue_segments}
                  tone="revenue"
                />
                <SegmentBars
                  title={`${activeCompany.ticker} cost inputs`}
                  subtitle={`Where ${activeCompany.ticker}'s money and operational risk go`}
                  data={activeCompany.cost_inputs}
                  tone="cost"
                />
              </section>
              <CompanyAtGlance company={activeCompany} chain={chain} />
            </>
          ) : null}

          <SectorComparison chain={chain} />

          <section className="al-glass p-5">
            <div className="flex items-center gap-2">
              <Activity className="size-4" aria-hidden style={{ color: "var(--al-gold)" }} />
              <h2 className="text-lg">Research use</h2>
            </div>
            <p className="mt-3 text-sm leading-7" style={{ color: "var(--al-on-surface-muted)" }}>
              Treat this as the structural map behind the weekly analysis. A headline on one company should be checked against customers, suppliers, revenue concentration, and cost exposure before it becomes a thesis.
            </p>
          </section>
        </>
      ) : null}
    </div>
  );
}
