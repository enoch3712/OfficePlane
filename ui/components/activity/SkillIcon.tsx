import {
  FileText, Presentation, FilePlus2, FileEdit, Search, Tag, ShieldCheck,
  Sparkles, MessageCircle, Activity as ActivityIcon, FileBox,
} from "lucide-react";

const map: Record<string, { Icon: typeof FileText; bg: string }> = {
  "generate-docx":            { Icon: FileText, bg: "bg-blue-900/30 text-blue-300" },
  "generate-pptx":            { Icon: Presentation, bg: "bg-orange-900/30 text-orange-300" },
  "generate-pdf":             { Icon: FileBox, bg: "bg-rose-900/30 text-rose-300" },
  "generate-from-collection": { Icon: FilePlus2, bg: "bg-purple-900/30 text-purple-300" },
  "document-edit":            { Icon: FileEdit, bg: "bg-emerald-900/30 text-emerald-300" },
  "vector-search":            { Icon: Search, bg: "bg-cyan-900/30 text-cyan-300" },
  "auto-categorize":          { Icon: Tag, bg: "bg-amber-900/30 text-amber-300" },
  "citation-validator":       { Icon: ShieldCheck, bg: "bg-lime-900/30 text-lime-300" },
  "rewrite-node":             { Icon: Sparkles, bg: "bg-fuchsia-900/30 text-fuchsia-300" },
  "grounded-chat":            { Icon: MessageCircle, bg: "bg-indigo-900/30 text-indigo-300" },
};

export function SkillIcon({ skill }: { skill: string }) {
  const entry = map[skill] ?? { Icon: ActivityIcon, bg: "bg-zinc-800 text-zinc-400" };
  const { Icon } = entry;
  return (
    <div className={`size-8 rounded-md flex items-center justify-center ${entry.bg}`}>
      <Icon className="size-4" />
    </div>
  );
}
