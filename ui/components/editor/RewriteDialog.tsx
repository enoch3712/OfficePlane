"use client";
import { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { rewriteNode } from "@/lib/api/rewrite";

export function RewriteDialog({
  open,
  onOpenChange,
  workspaceId,
  nodeId,
  currentText,
  onAccept,
}: {
  open: boolean;
  onOpenChange: (b: boolean) => void;
  workspaceId: string;
  nodeId: string;
  currentText: string;
  onAccept: (newNode: Record<string, unknown>) => Promise<void>;
}) {
  const [instruction, setInstruction] = useState("");
  const [tone, setTone] = useState("");
  const [preview, setPreview] = useState<Record<string, unknown> | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function runRewrite() {
    setBusy(true); setError(null);
    try {
      const r = await rewriteNode(workspaceId, nodeId, instruction, tone || undefined);
      setPreview(r.rewritten_node);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function accept() {
    if (!preview) return;
    setBusy(true);
    try {
      await onAccept(preview);
      onOpenChange(false);
      setPreview(null);
      setInstruction("");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Rewrite with AI</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <div>
            <div className="text-xs uppercase text-muted-foreground mb-1">Current</div>
            <div className="text-sm bg-muted/40 rounded p-2 max-h-32 overflow-auto">{currentText}</div>
          </div>
          <div>
            <label className="text-xs uppercase text-muted-foreground">Instruction</label>
            <Textarea
              placeholder="e.g. Make this more concise, or rewrite for a nursing audience"
              value={instruction}
              onChange={(e) => setInstruction(e.target.value)}
              disabled={busy}
              rows={3}
            />
          </div>
          <div>
            <label className="text-xs uppercase text-muted-foreground">Tone (optional)</label>
            <input
              className="flex h-10 w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm"
              placeholder="clinical / warm / authoritative / casual"
              value={tone}
              onChange={(e) => setTone(e.target.value)}
              disabled={busy}
            />
          </div>
          {error && <div className="text-sm text-red-400">{error}</div>}
          {preview && (
            <div>
              <div className="text-xs uppercase text-muted-foreground mb-1 flex items-center gap-2">
                <span>Suggested replacement</span>
                <Badge variant="accent" className="bg-[#5EFCAB]/15 text-[#5EFCAB]">preview</Badge>
              </div>
              <div className="text-sm bg-card/40 border border-border rounded p-2 max-h-48 overflow-auto whitespace-pre-wrap">
                {String((preview as Record<string, unknown>).text ?? JSON.stringify(preview, null, 2))}
              </div>
            </div>
          )}
        </div>
        <DialogFooter>
          {!preview && (
            <Button onClick={runRewrite} disabled={busy || !instruction.trim()}>
              {busy ? "Rewriting…" : "Rewrite"}
            </Button>
          )}
          {preview && (
            <>
              <Button variant="ghost" onClick={() => setPreview(null)} disabled={busy}>Try again</Button>
              <Button onClick={accept} disabled={busy} className="bg-[#5EFCAB] text-[#0F1116] hover:bg-[#5EFCAB]/90">
                {busy ? "Applying…" : "Accept"}
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
