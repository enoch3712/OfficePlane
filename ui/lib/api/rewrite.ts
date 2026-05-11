const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";

export interface RewriteResponse {
  workspace_id: string;
  node_id: string;
  original_node: Record<string, unknown>;
  rewritten_node: Record<string, unknown>;
  model: string;
}

export async function rewriteNode(
  workspaceId: string,
  nodeId: string,
  instruction: string,
  tone?: string,
): Promise<RewriteResponse> {
  const r = await fetch(`${API}/api/workspaces/${workspaceId}/rewrite-node`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ node_id: nodeId, instruction, tone }),
  });
  if (!r.ok) throw new Error(`rewrite failed: ${r.status} ${await r.text()}`);
  return r.json();
}
