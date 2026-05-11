import { ActivityFeed } from "@/components/activity/ActivityFeed";
import { Card } from "@/components/ui/card";

export default function ActivityPage() {
  return (
    <div className="h-[calc(100vh-4rem)] flex flex-col gap-4 p-6 overflow-hidden">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Activity</h1>
        <p className="text-sm text-muted-foreground">
          Every skill invocation across the agentic ECM, in chronological order.
        </p>
      </div>
      <Card className="flex-1 overflow-auto bg-card/40 p-6">
        <ActivityFeed />
      </Card>
    </div>
  );
}
