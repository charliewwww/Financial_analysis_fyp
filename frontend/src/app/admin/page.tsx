import Link from "next/link";

export const metadata = { title: "Admin Console — MarketPulse" };

const SECTIONS = [
  {
    href: "/admin/access",
    title: "Access management",
    blurb: "Approve waitlisted people, manage invites, and suspend accounts.",
  },
  {
    href: "/admin/pipeline",
    title: "Pipeline",
    blurb: "Trigger a sector run and watch the LangGraph stream live.",
  },
  {
    href: "/admin/system",
    title: "System health",
    blurb: "LLM provider, vector store, and external API configuration.",
  },
];

export default function AdminHome() {
  return (
    <div className="space-y-6">
      <header>
        <div className="al-eyebrow">Operator console</div>
        <h1 className="text-2xl">Admin</h1>
        <p
          className="text-sm mt-1"
          style={{ color: "var(--al-on-surface-muted)" }}
        >
          Tools that are intentionally hidden from normal users. Everything
          here is read-mostly, but actions taken affect production data.
        </p>
      </header>

      <div className="grid gap-4 md:grid-cols-2">
        {SECTIONS.map((s) => (
          <Link
            key={s.href}
            href={s.href}
            className="al-glass p-5 hover:-translate-y-0.5 transition-transform"
          >
            <div className="al-section-title text-base">{s.title}</div>
            <p
              className="text-sm mt-2"
              style={{ color: "var(--al-on-surface-muted)" }}
            >
              {s.blurb}
            </p>
          </Link>
        ))}
      </div>
    </div>
  );
}
