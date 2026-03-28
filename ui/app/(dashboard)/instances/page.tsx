'use client'

import { InstancesPanel } from '@/components/InstancesPanel'
import { useWebSocket } from '@/hooks/useWebSocket'
import { PageHeader } from '@/components/ui/page-header'
import { StatusIndicator } from '@/components/ui/status-indicator'

export default function InstancesPage() {
  const { status } = useWebSocket()

  return (
    <div className="max-w-6xl mx-auto">
      <PageHeader
        title="Instances"
        subtitle="Active document instances and their state"
        breadcrumbs={[{ label: 'Dashboard' }, { label: 'Instances' }]}
        status={
          <StatusIndicator
            status={status === 'connected' ? 'active' : 'pending'}
            label={status === 'connected' ? 'Live' : 'Offline'}
          />
        }
      />

      <InstancesPanel />
    </div>
  )
}
