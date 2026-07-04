import type { AgentSummary } from "@/types/api";

const AGENT_ORDER = new Map([
  ["Value Analyst", 0],
  ["Momentum Analyst", 1],
  ["Supply Chain Analyst", 2],
  ["Risk Analyst", 3],
]);

export function sortAgents(items: AgentSummary[]): AgentSummary[] {
  return [...items].sort((a, b) => {
    const aOrder = AGENT_ORDER.get(a.name) ?? 99;
    const bOrder = AGENT_ORDER.get(b.name) ?? 99;
    return aOrder - bOrder || a.name.localeCompare(b.name);
  });
}
