const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";

export interface DiffEntry {
  id: string;
  type: string;
  parent_id?: string | null;
  node?: Record<string, unknown>;
  before?: Record<string, unknown>;
  after?: Record<string, unknown>;
}

export interface DiffResponse {
  workspace_id: string;
  from_revision: number;
  to_revision: number;
  from_op: string;
  to_op: string;
  diff: {
    added: DiffEntry[];
    removed: DiffEntry[];
    changed: DiffEntry[];
    summary: { added_count: number; removed_count: number; changed_count: number };
  };
}

export async function fetchDiff(workspaceId: string, from: number, to: number): Promise<DiffResponse> {
  const r = await fetch(`${API}/api/workspaces/${workspaceId}/diff?from=${from}&to=${to}`, { cache: "no-store" });
  if (!r.ok) throw new Error(`diff fetch failed: ${r.status}`);
  return r.json();
}
