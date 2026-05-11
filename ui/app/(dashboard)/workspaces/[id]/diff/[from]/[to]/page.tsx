import { DiffView } from "@/components/diff/DiffView";
import { Card } from "@/components/ui/card";

export default async function DiffPage({ params }: { params: Promise<{ id: string; from: string; to: string }> }) {
  const { id, from, to } = await params;
  return (
    <div className="h-[calc(100vh-4rem)] flex flex-col gap-4 p-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Revision diff</h1>
        <p className="text-sm text-muted-foreground">
          Revision <strong>{from}</strong> → <strong>{to}</strong> · workspace <code className="text-xs">{id}</code>
        </p>
      </div>
      <Card className="flex-1 overflow-hidden bg-card/40">
        <div className="h-full overflow-auto p-6">
          <DiffView workspaceId={id} from={Number(from)} to={Number(to)} />
        </div>
      </Card>
    </div>
  );
}
