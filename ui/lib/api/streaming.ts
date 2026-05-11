const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";

export interface ProgressEvent {
  step: string;
  label: string;
  timestamp: number;
  [key: string]: unknown;
}

export type StreamHandler = (event: { name: string; data: Record<string, unknown> }) => void;

export async function streamSkill(
  skillName: string,
  inputs: Record<string, unknown>,
  onEvent: StreamHandler,
  signal?: AbortSignal,
): Promise<void> {
  const r = await fetch(`${API}/api/jobs/stream/${skillName}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify({ inputs }),
    signal,
  });
  if (!r.ok || !r.body) throw new Error(`stream open failed: ${r.status}`);

  const reader = r.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let idx: number;
    while ((idx = buf.indexOf("\n\n")) !== -1) {
      const block = buf.slice(0, idx).trim();
      buf = buf.slice(idx + 2);
      if (!block) continue;
      let eventName = "message";
      const dataLines: string[] = [];
      for (const line of block.split("\n")) {
        if (line.startsWith("event:")) eventName = line.slice(6).trim();
        else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
      }
      const dataStr = dataLines.join("\n");
      let data: Record<string, unknown> = {};
      try { data = dataStr ? JSON.parse(dataStr) : {}; } catch { data = { _raw: dataStr }; }
      onEvent({ name: eventName, data });
      if (eventName === "done" || eventName === "error") return;
    }
  }
}
