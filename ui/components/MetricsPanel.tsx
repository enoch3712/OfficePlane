'use client'

import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { CardStats, StatItem } from '@/components/ui/card'
import { LoadingState } from '@/components/ui/loading-state'

export function MetricsPanel() {
  const { data: metrics, isLoading } = useQuery({
    queryKey: ['metrics'],
    queryFn: () => api.getMetrics(),
  })

  if (isLoading) {
    return <LoadingState rows={2} />
  }

  const stats = [
    {
      label: 'Active Instances',
      value: metrics?.instances.byState.OPEN || 0,
      detail: `of ${metrics?.instances.total || 0}`,
    },
    {
      label: 'Queued Tasks',
      value: metrics?.tasks.byState.QUEUED || 0,
      detail: `of ${metrics?.tasks.total || 0}`,
    },
    {
      label: 'Running Tasks',
      value: metrics?.tasks.byState.RUNNING || 0,
      detail: `of ${metrics?.tasks.total || 0}`,
    },
    {
      label: 'Completed',
      value: metrics?.tasks.byState.COMPLETED || 0,
      detail: `of ${metrics?.tasks.total || 0}`,
    },
    {
      label: 'Failed',
      value: metrics?.tasks.byState.FAILED || 0,
      detail: `of ${metrics?.tasks.total || 0}`,
    },
    {
      label: 'Avg Duration',
      value: metrics?.tasks.avgDurationMs
        ? `${(metrics.tasks.avgDurationMs / 1000).toFixed(2)}s`
        : '0s',
    },
    {
      label: 'Memory Usage',
      value: metrics?.system.memoryUsageMb
        ? `${metrics.system.memoryUsageMb.toFixed(0)} MB`
        : '0 MB',
    },
    {
      label: 'CPU Usage',
      value: metrics?.system.cpuPercent
        ? `${metrics.system.cpuPercent.toFixed(1)}%`
        : '0%',
    },
  ]

  return (
    <CardStats>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-6">
        {stats.map((stat) => (
          <StatItem
            key={stat.label}
            label={stat.label}
            value={stat.value}
            detail={stat.detail}
          />
        ))}
      </div>
    </CardStats>
  )
}
