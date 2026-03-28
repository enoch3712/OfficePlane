'use client'

import { AgenticChat } from '@/components/AgenticChat'
import { useWebSocket } from '@/hooks/useWebSocket'
import { PageHeader } from '@/components/ui/page-header'
import { StatusIndicator } from '@/components/ui/status-indicator'

export default function ChatPage() {
  const { status } = useWebSocket()

  return (
    <div className="max-w-4xl mx-auto">
      <PageHeader
        title="Chat"
        subtitle="Agentic document manipulation"
        breadcrumbs={[{ label: 'Dashboard' }, { label: 'Chat' }]}
        status={
          <StatusIndicator
            status={status === 'connected' ? 'active' : 'pending'}
            label={status === 'connected' ? 'Live' : 'Offline'}
          />
        }
      />

      <AgenticChat />
    </div>
  )
}
