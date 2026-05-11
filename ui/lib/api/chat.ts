const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface Citation {
  index: number;
  chunk_id: string;
  document_id: string;
  text_excerpt: string;
  score: number;
}

export interface GroundedChatResponse {
  answer: string;
  citations: Citation[];
  mode: "grounded" | "ungrounded";
  model: string;
  retrieval_count: number;
}

export interface GroundedChatRequest {
  query: string;
  document_ids?: string[];
  collection_id?: string;
  history?: ChatMessage[];
  top_k?: number;
}

export async function groundedChat(req: GroundedChatRequest): Promise<GroundedChatResponse> {
  const r = await fetch(`${API}/api/chat/grounded`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!r.ok) throw new Error(`chat failed: ${r.status} ${await r.text()}`);
  return r.json();
}
