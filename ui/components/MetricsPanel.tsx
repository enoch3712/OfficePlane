'use client'

import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { FileText, List, CheckCircle, XCircle, Clock, Cpu, HardDrive } from 'lucide-react'

export function MetricsPanel() {
  const { data: metrics, isLoading } = useQuery({
    queryKey: ['metrics'],
    queryFn: () => api.getMetrics(),
  })

  if (isLoading) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-6 bg-gray-200 rounded w-32" />
          <div className="grid grid-cols-4 gap-4">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-24 bg-gray-100 rounded" />
            ))}
          </div>
        </div>
      </div>
    )
  }

  const stats = [
    {
      label: 'Active Instances',
      value: metrics?.instances.byState.OPEN || 0,
      total: metrics?.instances.total || 0,
      icon: FileText,
      color: 'text-primary-600',
      bgColor: 'bg-primary-50',
    },
    {
      label: 'Queued Tasks',
      value: metrics?.tasks.byState.QUEUED || 0,
      total: metrics?.tasks.total || 0,
      icon: Clock,
      color: 'text-warning-600',
      bgColor: 'bg-warning-50',
    },
    {
      label: 'Running Tasks',
      value: metrics?.tasks.byState.RUNNING || 0,
      total: metrics?.tasks.total || 0,
      icon: List,
      color: 'text-primary-600',
      bgColor: 'bg-primary-50',
    },
    {
      label: 'Completed',
      value: metrics?.tasks.byState.COMPLETED || 0,
      total: metrics?.tasks.total || 0,
      icon: CheckCircle,
      color: 'text-success-600',
      bgColor: 'bg-success-50',
    },
    {
      label: 'Failed',
      value: metrics?.tasks.byState.FAILED || 0,
      total: metrics?.tasks.total || 0,
      icon: XCircle,
      color: 'text-error-600',
      bgColor: 'bg-error-50',
    },
    {
      label: 'Avg Duration',
      value: metrics?.tasks.avgDurationMs
        ? `${(metrics.tasks.avgDurationMs / 1000).toFixed(2)}s`
        : '0s',
      icon: Clock,
      color: 'text-gray-600',
      bgColor: 'bg-gray-50',
    },
    {
      label: 'Memory Usage',
      value: metrics?.system.memoryUsageMb
        ? `${metrics.system.memoryUsageMb.toFixed(0)} MB`
        : '0 MB',
      icon: HardDrive,
      color: 'text-gray-600',
      bgColor: 'bg-gray-50',
    },
    {
      label: 'CPU Usage',
      value: metrics?.system.cpuPercent
        ? `${metrics.system.cpuPercent.toFixed(1)}%`
        : '0%',
      icon: Cpu,
      color: 'text-gray-600',
      bgColor: 'bg-gray-50',
    },
  ]

  return (
    <div className="bg-white rounded-lg shadow">
      <div className="p-6 border-b border-gray-200">
        <h2 className="text-lg font-semibold text-gray-900">System Metrics</h2>
      </div>

      <div className="p-6">
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-4">
          {stats.map((stat) => {
            const Icon = stat.icon
            return (
              <div
                key={stat.label}
                className="flex flex-col gap-2 p-4 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors"
              >
                <div className="flex items-center gap-2">
                  <div className={`p-2 ${stat.bgColor} rounded`}>
                    <Icon className={`w-4 h-4 ${stat.color}`} />
                  </div>
                </div>
                <div>
                  <div className="text-2xl font-bold text-gray-900">{stat.value}</div>
                  {stat.total !== undefined && (
                    <div className="text-xs text-gray-500">of {stat.total}</div>
                  )}
                  <div className="text-xs text-gray-600 mt-1">{stat.label}</div>
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
