import { Badge } from "@/components/ui/badge";
import { DocumentStatus } from "@/lib/api/lifecycle";

const styles: Record<DocumentStatus, string> = {
  DRAFT: "bg-zinc-700/40 text-zinc-200 border border-zinc-600",
  REVIEW: "bg-amber-900/30 text-amber-200 border border-amber-700",
  APPROVED: "bg-[#5EFCAB]/15 text-[#5EFCAB] border border-[#5EFCAB]/40",
  ARCHIVED: "bg-zinc-900/60 text-zinc-500 border border-zinc-700 line-through",
};

export function StatusBadge({ status }: { status: DocumentStatus }) {
  return (
    <Badge className={`text-xs ${styles[status]}`}>
      {status.toLowerCase()}
    </Badge>
  );
}
