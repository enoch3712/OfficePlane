const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";

export type DocumentStatus = "DRAFT" | "REVIEW" | "APPROVED" | "ARCHIVED";

export interface TransitionResponse {
  document_id: string;
  from_status: DocumentStatus;
  to_status: DocumentStatus;
  event_id: string;
  created_at: string;
}

export async function transitionDocument(
  id: string, to: DocumentStatus, actor?: string, note?: string,
): Promise<TransitionResponse> {
  const r = await fetch(`${API}/api/documents/${id}/transition`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ to_status: to, actor, note }),
  });
  if (!r.ok) throw new Error(`transition failed: ${r.status} ${await r.text()}`);
  return r.json();
}

export interface StatusHistoryEntry {
  id: string;
  from_status: DocumentStatus | null;
  to_status: DocumentStatus;
  actor: string | null;
  note: string | null;
  created_at: string;
}

export async function fetchStatusHistory(id: string): Promise<{
  document_id: string;
  current_status: DocumentStatus;
  events: StatusHistoryEntry[];
}> {
  const r = await fetch(`${API}/api/documents/${id}/status-history`);
  if (!r.ok) throw new Error(`history failed: ${r.status}`);
  return r.json();
}
