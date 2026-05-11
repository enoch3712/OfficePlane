import { GroundedChat } from "@/components/chat/GroundedChat";

export default function ChatPage() {
  return (
    <div className="h-[calc(100vh-4rem)] flex flex-col gap-4 p-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Ask your documents</h1>
        <p className="text-sm text-muted-foreground">
          Grounded answers with source citations.
        </p>
      </div>
      <div className="flex-1 overflow-hidden rounded-lg border border-border bg-card/40">
        <GroundedChat />
      </div>
    </div>
  );
}
