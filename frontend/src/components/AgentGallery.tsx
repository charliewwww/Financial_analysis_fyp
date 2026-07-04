"use client";

import Link from "next/link";
import type { FormEvent } from "react";
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, FilePenLine, PlayCircle } from "lucide-react";

import { createAgentSkill, fetchAgents } from "@/lib/api";
import { sortAgents } from "@/lib/agent-catalog";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Pill } from "@/components/primitives";

export function AgentGallery() {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [skillContent, setSkillContent] = useState("");

  const agents = useQuery({
    queryKey: ["agents"],
    queryFn: fetchAgents,
    retry: false,
    staleTime: 60_000,
  });

  const items = useMemo(
    () => sortAgents(agents.data ?? []),
    [agents.data]
  );

  const createSkill = useMutation({
    mutationFn: () => {
      const cleanName = name.trim();
      return createAgentSkill({
        name: cleanName,
        description: description.trim() || null,
        skill_name: `${cleanName} Skill`,
        skill_type: "domain",
        skill_content: skillContent.trim(),
      });
    },
    onSuccess: () => {
      setName("");
      setDescription("");
      setSkillContent("");
      queryClient.invalidateQueries({ queryKey: ["agents"] });
    },
  });

  const canCreate = name.trim().length >= 3 && skillContent.trim().length >= 40 && !createSkill.isPending;

  function submitSkill(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canCreate) return;
    createSkill.mutate();
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <div className="al-eyebrow">Analyst gallery</div>
          <h1 className="text-3xl md:text-4xl">Agents</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6" style={{ color: "var(--al-on-surface-muted)" }}>
            Built-in analysts are seeded by the backend registry and reused across ticker boards and pipeline runs.
          </p>
        </div>
        <Link href="/tickers">
          <Button className="al-gold-gradient rounded-full px-4">
            <PlayCircle data-icon="inline-start" className="size-4" aria-hidden />
            Test on ticker
          </Button>
        </Link>
      </header>

      {agents.isLoading ? (
        <div className="grid gap-4 md:grid-cols-2">
          {Array.from({ length: 4 }).map((_, index) => (
            <Skeleton key={index} className="h-44 rounded-lg" />
          ))}
        </div>
      ) : agents.isError ? (
        <div className="al-glass flex flex-col items-center gap-3 p-8 text-center">
          <p className="text-sm font-semibold">Couldn&apos;t load analysts.</p>
          <p className="text-sm" style={{ color: "var(--al-on-surface-muted)" }}>
            The backend didn&apos;t respond. No data is shown to avoid displaying anything inaccurate.
          </p>
          <Button variant="outline" className="rounded-full px-4" onClick={() => agents.refetch()}>
            Retry
          </Button>
        </div>
      ) : items.length === 0 ? (
        <div className="al-glass flex flex-col items-center gap-2 p-8 text-center">
          <p className="text-sm font-semibold">No analysts yet.</p>
          <p className="text-sm" style={{ color: "var(--al-on-surface-muted)" }}>
            Create your first custom analyst below to get started.
          </p>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {items.map((agent) => (
            <article key={agent.id} className="al-glass flex min-h-[180px] flex-col p-5">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="al-section-title text-base">{agent.name}</div>
                  <p className="mt-2 text-sm leading-6" style={{ color: "var(--al-on-surface-muted)" }}>
                    {agent.description ?? "Specialist MarketPulse analyst."}
                  </p>
                </div>
                <Pill variant={agent.is_builtin ? "gold" : "green"}>
                  {agent.is_builtin ? "built-in" : "custom"}
                </Pill>
              </div>
              <div className="mt-auto flex items-center justify-between gap-3 pt-5">
                <span className="text-xs tabular-nums" style={{ color: "var(--al-on-surface-muted)" }}>
                  Agent #{agent.id}
                </span>
                <Link
                  href={`/tickers`}
                  className="inline-flex items-center gap-1 text-sm font-semibold hover:underline"
                  style={{ color: "var(--al-gold)" }}
                >
                  Open board <ArrowRight className="size-4" aria-hidden />
                </Link>
              </div>
            </article>
          ))}
        </div>
      )}

      <section className="al-glass p-5">
        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div className="flex items-center gap-3">
            <FilePenLine className="size-5" style={{ color: "var(--al-gold)" }} aria-hidden />
            <div>
              <div className="al-section-title text-base">Skill editor</div>
              <p className="text-sm" style={{ color: "var(--al-on-surface-muted)" }}>
                Create a custom analyst lane for the Decision Desk.
              </p>
            </div>
          </div>
          <Pill variant="green">custom agent</Pill>
        </div>

        <form onSubmit={submitSkill} className="mt-5 grid gap-3 lg:grid-cols-[0.85fr_1.15fr]">
          <div className="space-y-3">
            <label className="block text-sm font-semibold" htmlFor="agent-name">Agent name</label>
            <input
              id="agent-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              className="h-10 w-full rounded-lg border border-border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
              placeholder="Options Flow Analyst"
            />

            <label className="block text-sm font-semibold" htmlFor="agent-description">Description</label>
            <input
              id="agent-description"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              className="h-10 w-full rounded-lg border border-border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
              placeholder="Tracks volatility, flow, and positioning."
            />
          </div>

          <div className="space-y-3">
            <label className="block text-sm font-semibold" htmlFor="skill-content">Skill instructions</label>
            <textarea
              id="skill-content"
              value={skillContent}
              onChange={(event) => setSkillContent(event.target.value)}
              className="min-h-32 w-full resize-y rounded-lg border border-border bg-background px-3 py-2 text-sm leading-6 outline-none focus:ring-2 focus:ring-ring"
              placeholder="Focus on options volume, implied volatility, dealer gamma, and how positioning changes the next market move."
            />
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-xs" style={{ color: "var(--al-on-surface-muted)" }}>
                {createSkill.isSuccess ? "Skill agent created. It will join the next board run." : "Minimum 40 characters."}
              </p>
              <Button type="submit" variant="outline" className="self-start rounded-full px-4 sm:self-auto" disabled={!canCreate}>
                <FilePenLine data-icon="inline-start" className="size-4" aria-hidden />
                {createSkill.isPending ? "Creating" : "Create skill"}
              </Button>
            </div>
            {createSkill.isError ? (
              <p role="alert" className="text-sm text-destructive">
                {createSkill.error instanceof Error ? createSkill.error.message : "Could not create skill."}
              </p>
            ) : null}
          </div>
        </form>
      </section>
    </div>
  );
}
