"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { ActivityEvent, fetchActivity, fetchKnownSkills } from "@/lib/api/activity";
import { SkillIcon } from "./SkillIcon";

const REFRESH_MS = 5000;

function timeAgo(iso: string): string {
  const ms = Date.now() - new Date(iso).getTime();
  if (ms < 60_000) return `${Math.floor(ms / 1000)}s ago`;
  if (ms < 3_600_000) return `${Math.floor(ms / 60_000)}m ago`;
  if (ms < 86_400_000) return `${Math.floor(ms / 3_600_000)}h ago`;
  return `${Math.floor(ms / 86_400_000)}d ago`;
}

export function ActivityFeed() {
  const [events, setEvents] = useState<ActivityEvent[]>([]);
  const [total, setTotal] = useState(0);
  const [skillFilter, setSkillFilter] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<"" | "ok" | "error">("");
  const [knownSkills, setKnownSkills] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      const r = await fetchActivity({
        limit: 100,
        skill: skillFilter || undefined,
        status: statusFilter || undefined,
      });
      setEvents(r.events);
      setTotal(r.total_count);
      setError(null);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchKnownSkills().then(setKnownSkills).catch(() => {});
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, REFRESH_MS);
    return () => clearInterval(id);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [skillFilter, statusFilter]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <select
          className="h-9 rounded-md border border-input bg-transparent px-3 text-sm"
          value={skillFilter}
          onChange={(e) => setSkillFilter(e.target.value)}
        >
          <option value="">All skills</option>
          {knownSkills.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
        <select
          className="h-9 rounded-md border border-input bg-transparent px-3 text-sm"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as "" | "ok" | "error")}
        >
          <option value="">All statuses</option>
          <option value="ok">OK</option>
          <option value="error">Error</option>
        </select>
        <div className="text-xs text-muted-foreground">
          {loading ? "Loading…" : `${events.length} of ${total.toLocaleString()} events · refreshes every 5s`}
        </div>
      </div>

      {error && <div className="text-sm text-red-400">{error}</div>}

      <ol className="space-y-2">
        {events.map((e) => (
          <li key={e.id} className="flex items-start gap-3 p-3 rounded-md border border-border bg-card/40">
            <SkillIcon skill={e.skill} />
            <div className="flex-1 min-w-0">
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <span className="font-medium">{e.skill}</span>
                <Badge
                  variant={e.status === "ok" ? "neutral" : "error"}
                  className={
                    e.status === "ok"
                      ? "bg-[#5EFCAB]/15 text-[#5EFCAB]"
                      : "bg-red-900/30 text-red-200"
                  }
                >{e.status}</Badge>
                {e.duration_ms !== null && (
                  <span className="text-xs text-muted-foreground">{e.duration_ms}ms</span>
                )}
                {e.model && <span className="text-xs text-muted-foreground">· {e.model}</span>}
                <span className="text-xs text-muted-foreground ml-auto">{timeAgo(e.timestamp)}</span>
              </div>
              <div className="text-sm text-foreground/80 mt-1 truncate">{e.summary}</div>
              {e.workspace_id && (
                <div className="text-xs text-muted-foreground mt-1">
                  workspace <code className="text-xs">{e.workspace_id.slice(0, 8)}</code>
                  {" · "}
                  <Link href={`/lineage/${e.workspace_id}`} className="text-primary hover:underline">
                    lineage
                  </Link>
                </div>
              )}
              {e.error_message && (
                <div className="text-xs text-red-400 mt-1 truncate">{e.error_message}</div>
              )}
            </div>
          </li>
        ))}
        {!loading && events.length === 0 && (
          <li className="text-sm text-muted-foreground p-4 text-center">No activity yet.</li>
        )}
      </ol>
    </div>
  );
}
