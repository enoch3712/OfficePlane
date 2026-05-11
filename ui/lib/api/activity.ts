const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";

export interface ActivityEvent {
  id: string;
  timestamp: string;
  skill: string;
  model: string | null;
  actor: string | null;
  status: "ok" | "error";
  duration_ms: number | null;
  workspace_id: string | null;
  error_message: string | null;
  summary: string;
}

export interface ActivityResponse {
  total_count: number;
  page_count: number;
  limit: number;
  offset: number;
  filters: {
    skill: string | null;
    status: string | null;
    workspace_id: string | null;
    since_minutes: number | null;
  };
  skill_counts_in_page: Record<string, number>;
  status_counts_in_page: Record<string, number>;
  events: ActivityEvent[];
}

export interface ActivityQuery {
  limit?: number;
  offset?: number;
  skill?: string;
  status?: "ok" | "error";
  workspace_id?: string;
  since_minutes?: number;
}

export async function fetchActivity(q: ActivityQuery = {}): Promise<ActivityResponse> {
  const params = new URLSearchParams();
  if (q.limit) params.set("limit", String(q.limit));
  if (q.offset) params.set("offset", String(q.offset));
  if (q.skill) params.set("skill", q.skill);
  if (q.status) params.set("status", q.status);
  if (q.workspace_id) params.set("workspace_id", q.workspace_id);
  if (q.since_minutes) params.set("since_minutes", String(q.since_minutes));
  const r = await fetch(`${API}/api/activity?${params.toString()}`, { cache: "no-store" });
  if (!r.ok) throw new Error(`activity fetch failed: ${r.status}`);
  return r.json();
}

export async function fetchKnownSkills(): Promise<string[]> {
  const r = await fetch(`${API}/api/activity/skills`, { cache: "no-store" });
  if (!r.ok) throw new Error(`skills fetch failed: ${r.status}`);
  return (await r.json()).skills;
}
