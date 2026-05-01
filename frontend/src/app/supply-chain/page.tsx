"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Sankey, Tooltip, ResponsiveContainer } from "recharts";
import {
  fetchSupplyChain,
  fetchSupplyChainSectors,
  type SupplyChainData,
} from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";

function buildSankey(data: SupplyChainData) {
  const nameToIndex = new Map<string, number>();
  const nodes: Array<{ name: string }> = [];
  const ensure = (name: string) => {
    if (!nameToIndex.has(name)) {
      nameToIndex.set(name, nodes.length);
      nodes.push({ name });
    }
    return nameToIndex.get(name)!;
  };
  const links = data.key_flows.map((f) => ({
    source: ensure(f.from),
    target: ensure(f.to),
    value: Math.max(1, f.value),
  }));
  return { nodes, links };
}

export default function SupplyChainPage() {
  const { data: sectors } = useQuery({
    queryKey: ["supply-chain", "sectors"],
    queryFn: fetchSupplyChainSectors,
    staleTime: 5 * 60 * 1000,
  });

  const [selected, setSelected] = useState<string | null>(null);
  const sectorId = selected ?? sectors?.[0]?.id ?? null;

  const {
    data: chain,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["supply-chain", sectorId],
    queryFn: () => fetchSupplyChain(sectorId!),
    enabled: !!sectorId,
  });

  const sankey = useMemo(() => (chain ? buildSankey(chain) : null), [chain]);

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold">Supply Chain</h1>
          <p className="text-sm text-muted-foreground">
            Curated topology — revenue segments, cost inputs, and inter-company
            flows.
          </p>
        </div>
        <label className="text-sm flex flex-col gap-1">
          <span className="text-muted-foreground">Sector</span>
          <select
            className="bg-background border rounded px-2 py-1 text-sm min-w-56"
            value={sectorId ?? ""}
            onChange={(e) => setSelected(e.target.value)}
            disabled={!sectors}
          >
            {(sectors ?? []).map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </label>
      </div>

      {isLoading && <Skeleton className="h-96 w-full" />}
      {isError && (
        <p className="text-sm text-red-400">Failed to load supply chain.</p>
      )}

      {chain && sankey && sankey.links.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Inter-company flows</CardTitle>
          </CardHeader>
          <CardContent className="h-[500px]">
            <ResponsiveContainer width="100%" height="100%">
              <Sankey
                data={sankey}
                nodePadding={28}
                margin={{ top: 8, right: 80, bottom: 8, left: 80 }}
                link={{ stroke: "#6366f1", strokeOpacity: 0.4 } as never}
                node={{ fill: "#818cf8" } as never}
              >
                <Tooltip />
              </Sankey>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      )}

      {chain && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Companies</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {chain.companies.map((c) => (
              <div key={c.ticker} className="border rounded-md p-4 space-y-3">
                <div className="flex items-center justify-between flex-wrap gap-2">
                  <div>
                    <span className="font-mono text-sm font-semibold">
                      {c.ticker}
                    </span>
                    <span className="ml-2 text-sm text-muted-foreground">
                      {c.name}
                    </span>
                  </div>
                  {c.layer && (
                    <Badge variant="outline" className="text-xs">
                      {c.layer}
                    </Badge>
                  )}
                </div>

                {c.products.length > 0 && (
                  <div className="text-xs text-muted-foreground">
                    <span className="font-medium">Products:</span>{" "}
                    {c.products.join(", ")}
                  </div>
                )}

                <div className="grid md:grid-cols-2 gap-4">
                  <div>
                    <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-1">
                      Revenue segments
                    </h4>
                    <ul className="space-y-1 text-xs">
                      {Object.entries(c.revenue_segments).map(([k, v]) => (
                        <li key={k} className="flex justify-between gap-2">
                          <span className="truncate">{k}</span>
                          <span className="font-mono">{v.pct}%</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                  <div>
                    <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-1">
                      Cost inputs
                    </h4>
                    <ul className="space-y-1 text-xs">
                      {Object.entries(c.cost_inputs).map(([k, v]) => (
                        <li key={k} className="flex justify-between gap-2">
                          <span className="truncate">{k}</span>
                          <span className="font-mono">{v.pct}%</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
