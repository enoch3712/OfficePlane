'use client'

import { HistoryPanel } from '@/components/HistoryPanel'
import { useWebSocket } from '@/hooks/useWebSocket'
import { PageHeader } from '@/components/ui/page-header'
import { StatusIndicator } from '@/components/ui/status-indicator'

export default function ActivityPage() {
  const { status, events } = useWebSocket()

  return (
    <div className="max-w-6xl mx-auto">
      <PageHeader
        title="Activity"
        subtitle="Recent events and state transitions"
        breadcrumbs={[{ label: 'Dashboard' }, { label: 'Activity' }]}
        status={
          <StatusIndicator
            status={status === 'connected' ? 'active' : 'pending'}
            label={status === 'connected' ? 'Live' : 'Offline'}
          />
        }
      />

      <HistoryPanel recentEvents={events} />
    </div>
  )
}
