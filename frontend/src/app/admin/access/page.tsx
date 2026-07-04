"use client";

import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  ApiError,
  addAllowlist,
  approveAccessRequest,
  denyAccessRequest,
  fetchAccessRequests,
  fetchAllowlist,
  fetchUsers,
  reactivateUser,
  removeAllowlist,
  setUserRole,
  suspendUser,
} from "@/lib/api";

const mutedStyle = { color: "var(--al-on-surface-muted)" } as const;
const btnPrimary =
  "al-gold-gradient rounded-full px-3 py-1.5 text-xs font-semibold disabled:opacity-50";
const btnGhost =
  "rounded-full border border-border px-3 py-1.5 text-xs hover:bg-muted/40 disabled:opacity-50";
const btnDanger =
  "rounded-full border border-border px-3 py-1.5 text-xs text-red-500 hover:bg-muted/40 disabled:opacity-50";

export default function AdminAccessPage() {
  const qc = useQueryClient();
  const refresh = React.useCallback(() => {
    qc.invalidateQueries({ queryKey: ["admin"] });
  }, [qc]);

  const requests = useQuery({
    queryKey: ["admin", "access-requests", "pending"],
    queryFn: () => fetchAccessRequests("pending"),
  });
  const allowlist = useQuery({
    queryKey: ["admin", "allowlist"],
    queryFn: fetchAllowlist,
  });
  const users = useQuery({
    queryKey: ["admin", "users"],
    queryFn: fetchUsers,
  });

  const [email, setEmail] = React.useState("");
  const [role, setRole] = React.useState<"user" | "admin">("user");
  const [error, setError] = React.useState<string | null>(null);

  const onError = (e: unknown) =>
    setError(
      e instanceof ApiError ? e.detail : "Something went wrong. Please try again."
    );

  const approve = useMutation({
    mutationFn: approveAccessRequest,
    onSuccess: refresh,
    onError,
  });
  const deny = useMutation({
    mutationFn: denyAccessRequest,
    onSuccess: refresh,
    onError,
  });
  const invite = useMutation({
    mutationFn: () => addAllowlist({ email: email.trim().toLowerCase(), role }),
    onSuccess: () => {
      setEmail("");
      setRole("user");
      setError(null);
      refresh();
    },
    onError,
  });
  const remove = useMutation({
    mutationFn: removeAllowlist,
    onSuccess: refresh,
    onError,
  });
  const suspend = useMutation({
    mutationFn: suspendUser,
    onSuccess: refresh,
    onError,
  });
  const reactivate = useMutation({
    mutationFn: reactivateUser,
    onSuccess: refresh,
    onError,
  });
  const changeRole = useMutation({
    mutationFn: (v: { email: string; role: "user" | "admin" }) =>
      setUserRole(v.email, v.role),
    onSuccess: refresh,
    onError,
  });

  const pending = requests.data ?? [];
  const invited = allowlist.data ?? [];
  const people = users.data ?? [];

  return (
    <div className="space-y-8">
      <header>
        <div className="al-eyebrow">Operator console</div>
        <h1 className="text-2xl">Access management</h1>
        <p className="text-sm mt-1" style={mutedStyle}>
          Approve people into the private beta, manage invites, and suspend
          accounts. Changes take effect immediately.
        </p>
      </header>

      {error && (
        <div
          className="rounded-lg border border-border px-4 py-3 text-sm"
          style={{ color: "var(--al-danger, #ef4444)" }}
        >
          {error}
        </div>
      )}

      {/* ── Waitlist ──────────────────────────────────────────── */}
      <section className="al-glass p-5 space-y-4">
        <div className="al-section-title text-base">
          Waitlist {pending.length > 0 ? `(${pending.length})` : ""}
        </div>
        {requests.isLoading ? (
          <p className="text-sm" style={mutedStyle}>
            Loading…
          </p>
        ) : pending.length === 0 ? (
          <p className="text-sm" style={mutedStyle}>
            No pending requests.
          </p>
        ) : (
          <ul className="divide-y divide-border">
            {pending.map((r) => (
              <li
                key={r.email}
                className="flex items-center justify-between gap-3 py-3"
              >
                <div className="min-w-0">
                  <div className="font-medium truncate">{r.name ?? r.email}</div>
                  <div className="text-xs truncate" style={mutedStyle}>
                    {r.email}
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <button
                    className={btnPrimary}
                    onClick={() => approve.mutate(r.email)}
                    disabled={approve.isPending}
                  >
                    Approve
                  </button>
                  <button
                    className={btnGhost}
                    onClick={() => deny.mutate(r.email)}
                    disabled={deny.isPending}
                  >
                    Deny
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* ── Invite + allow-list ───────────────────────────────── */}
      <section className="al-glass p-5 space-y-4">
        <div className="al-section-title text-base">Invited emails</div>
        <form
          className="flex flex-col gap-2 sm:flex-row"
          onSubmit={(e) => {
            e.preventDefault();
            if (email.trim()) invite.mutate();
          }}
        >
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="name@example.com"
            className="flex-1 rounded-md border border-border bg-background px-3 py-2 text-sm"
          />
          <select
            value={role}
            onChange={(e) => setRole(e.target.value as "user" | "admin")}
            className="rounded-md border border-border bg-background px-3 py-2 text-sm"
            aria-label="Role for the invited email"
          >
            <option value="user">User</option>
            <option value="admin">Admin</option>
          </select>
          <button
            type="submit"
            className="al-gold-gradient rounded-full px-4 py-2 text-sm font-semibold disabled:opacity-50"
            disabled={invite.isPending}
          >
            {invite.isPending ? "Inviting…" : "Invite"}
          </button>
        </form>

        {allowlist.isLoading ? (
          <p className="text-sm" style={mutedStyle}>
            Loading…
          </p>
        ) : invited.length === 0 ? (
          <p className="text-sm" style={mutedStyle}>
            No invited emails yet.
          </p>
        ) : (
          <ul className="divide-y divide-border">
            {invited.map((a) => (
              <li
                key={a.email}
                className="flex items-center justify-between gap-3 py-3"
              >
                <div className="min-w-0">
                  <div className="font-medium truncate">{a.email}</div>
                  <div className="text-xs" style={mutedStyle}>
                    {a.role === "admin" ? "Admin" : "User"}
                  </div>
                </div>
                <button
                  className={btnGhost}
                  onClick={() => remove.mutate(a.email)}
                  disabled={remove.isPending}
                >
                  Remove
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* ── Users ─────────────────────────────────────────────── */}
      <section className="al-glass p-5 space-y-4">
        <div className="al-section-title text-base">Users</div>
        {users.isLoading ? (
          <p className="text-sm" style={mutedStyle}>
            Loading…
          </p>
        ) : people.length === 0 ? (
          <p className="text-sm" style={mutedStyle}>
            No users have signed in yet.
          </p>
        ) : (
          <ul className="divide-y divide-border">
            {people.map((u) => (
              <li
                key={u.email}
                className="flex items-center justify-between gap-3 py-3"
              >
                <div className="min-w-0">
                  <div className="font-medium truncate">
                    {u.username ?? u.email}
                  </div>
                  <div className="text-xs truncate" style={mutedStyle}>
                    {u.email} · {u.role} · {u.status}
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {u.role === "admin" ? (
                    <button
                      className={btnGhost}
                      onClick={() =>
                        changeRole.mutate({ email: u.email, role: "user" })
                      }
                      disabled={changeRole.isPending}
                    >
                      Make user
                    </button>
                  ) : (
                    <button
                      className={btnGhost}
                      onClick={() =>
                        changeRole.mutate({ email: u.email, role: "admin" })
                      }
                      disabled={changeRole.isPending}
                    >
                      Make admin
                    </button>
                  )}
                  {u.status === "suspended" ? (
                    <button
                      className={btnPrimary}
                      onClick={() => reactivate.mutate(u.email)}
                      disabled={reactivate.isPending}
                    >
                      Reactivate
                    </button>
                  ) : (
                    <button
                      className={btnDanger}
                      onClick={() => suspend.mutate(u.email)}
                      disabled={suspend.isPending}
                    >
                      Suspend
                    </button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
