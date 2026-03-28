'use client'

import { TaskQueuePanel } from '@/components/TaskQueuePanel'
import { useWebSocket } from '@/hooks/useWebSocket'
import { PageHeader } from '@/components/ui/page-header'
import { StatusIndicator } from '@/components/ui/status-indicator'

export default function TasksPage() {
  const { status } = useWebSocket()

  return (
    <div className="max-w-6xl mx-auto">
      <PageHeader
        title="Task Queue"
        subtitle="Queued, running, and completed tasks"
        breadcrumbs={[{ label: 'Dashboard' }, { label: 'Task Queue' }]}
        status={
          <StatusIndicator
            status={status === 'connected' ? 'active' : 'pending'}
            label={status === 'connected' ? 'Live' : 'Offline'}
          />
        }
      />

      <TaskQueuePanel />
    </div>
  )
}
