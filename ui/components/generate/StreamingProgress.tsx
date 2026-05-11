"use client";
import { Badge } from "@/components/ui/badge";
import { ProgressEvent } from "@/lib/api/streaming";

export function StreamingProgress({ events, status }: {
  events: ProgressEvent[];
  status: "idle" | "running" | "done" | "error";
}) {
  if (status === "idle") return null;
  return (
    <div className="rounded-md border border-border bg-card/40 p-4 space-y-2">
      <div className="flex items-center gap-2">
        <Badge
          variant={status === "running" ? "warning" : status === "done" ? "success" : "error"}
          className={
            status === "running" ? "bg-amber-900/30 text-amber-200"
            : status === "done" ? "bg-[#5EFCAB]/15 text-[#5EFCAB]"
            : "bg-red-900/30 text-red-200"
          }
        >
          {status === "running" ? "Streaming…" : status === "done" ? "Complete" : "Error"}
        </Badge>
        <span className="text-xs text-muted-foreground">{events.length} step{events.length === 1 ? "" : "s"}</span>
      </div>
      <ol className="space-y-1 text-sm">
        {events.map((e, i) => (
          <li key={i} className="flex items-start gap-3">
            <span className="text-xs text-muted-foreground w-16 shrink-0">{e.step}</span>
            <span className="text-foreground">{e.label}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}
