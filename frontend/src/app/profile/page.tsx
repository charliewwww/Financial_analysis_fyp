"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchMe, updateMe } from "@/lib/api";
import type { UserUpdateRequest } from "@/types/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";

export default function ProfilePage() {
  const qc = useQueryClient();

  const {
    data: profile,
    isLoading,
    isError,
  } = useQuery({ queryKey: ["me"], queryFn: fetchMe, staleTime: 60_000 });

  const [username, setUsername] = useState<string>("");
  const [usernameEditing, setUsernameEditing] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: (body: UserUpdateRequest) => updateMe(body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["me"] });
      setUsernameEditing(false);
      setSaveError(null);
    },
    onError: (err: Error) => {
      setSaveError(err.message);
    },
  });

  if (isLoading) {
    return (
      <div className="space-y-6 max-w-2xl">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (isError || !profile) {
    return (
      <p className="text-destructive">
        Failed to load profile. Make sure you are authenticated.
      </p>
    );
  }

  function handleUsernameSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!username.trim()) return;
    mutation.mutate({ username: username.trim() });
  }

  return (
    <div className="space-y-8 max-w-2xl">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-semibold">Profile</h1>
        <p className="text-muted-foreground text-sm mt-1">{profile.email}</p>
      </div>

      {/* Identity card */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Display name</CardTitle>
        </CardHeader>
        <CardContent>
          {usernameEditing ? (
            <form onSubmit={handleUsernameSubmit} className="flex gap-2">
              <input
                autoFocus
                className="flex-1 rounded-md border border-input bg-background px-3 py-1.5 text-sm"
                defaultValue={profile.username ?? ""}
                maxLength={64}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Enter display name…"
              />
              <Button type="submit" size="sm" disabled={mutation.isPending}>
                Save
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => setUsernameEditing(false)}
              >
                Cancel
              </Button>
            </form>
          ) : (
            <div className="flex items-center gap-3">
              <span className="text-sm">
                {profile.username ?? (
                  <span className="text-muted-foreground italic">Not set</span>
                )}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setUsername(profile.username ?? "");
                  setUsernameEditing(true);
                }}
              >
                Edit
              </Button>
            </div>
          )}
          {saveError && (
            <p className="mt-2 text-xs text-destructive">{saveError}</p>
          )}
        </CardContent>
      </Card>

      {/* Account info */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Account</CardTitle>
        </CardHeader>
        <CardContent className="text-sm space-y-2 text-muted-foreground">
          <div className="flex justify-between">
            <span>Email</span>
            <span className="text-foreground">{profile.email}</span>
          </div>
          <div className="flex justify-between">
            <span>Member since</span>
            <span className="text-foreground">
              {new Date(profile.created_at).toLocaleDateString()}
            </span>
          </div>
          <div className="flex justify-between">
            <span>Authentication</span>
            <Badge variant="secondary">Cloudflare Access</Badge>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
