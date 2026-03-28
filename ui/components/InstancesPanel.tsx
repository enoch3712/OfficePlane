'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { InstanceState } from '@/lib/types'
import { FileText, StopCircle, Trash2 } from 'lucide-react'
import { TimeAgo } from './TimeAgo'
import { cn } from '@/lib/cn'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { StatusIndicator } from '@/components/ui/status-indicator'
import { EmptyState } from '@/components/ui/empty-state'
import { LoadingState } from '@/components/ui/loading-state'

type StatusIndicatorStatus = 'active' | 'completed' | 'error' | 'pending' | 'warning'

function getStatusIndicatorStatus(state: InstanceState): StatusIndicatorStatus {
  switch (state) {
    case InstanceState.OPEN:
    case InstanceState.IN_USE:
      return 'active'
    case InstanceState.IDLE:
      return 'completed'
    case InstanceState.OPENING:
    case InstanceState.CLOSING:
      return 'pending'
    case InstanceState.ERROR:
    case InstanceState.CRASHED:
      return 'error'
    default:
      return 'pending'
  }
}

function getBadgeVariant(state: InstanceState): 'accent' | 'warning' | 'neutral' | 'error' {
  switch (state) {
    case InstanceState.OPEN:
    case InstanceState.IN_USE:
      return 'accent'
    case InstanceState.OPENING:
    case InstanceState.CLOSING:
    case InstanceState.IDLE:
      return 'warning'
    case InstanceState.CLOSED:
      return 'neutral'
    case InstanceState.ERROR:
    case InstanceState.CRASHED:
      return 'error'
    default:
      return 'neutral'
  }
}

function getBorderColor(state: InstanceState): string {
  switch (state) {
    case InstanceState.OPEN:
    case InstanceState.IN_USE:
      return 'border-l-primary'
    case InstanceState.OPENING:
    case InstanceState.CLOSING:
      return 'border-l-amber-400'
    case InstanceState.CLOSED:
    case InstanceState.IDLE:
      return 'border-l-muted-foreground/30'
    case InstanceState.ERROR:
    case InstanceState.CRASHED:
      return 'border-l-red-500'
    default:
      return 'border-l-muted-foreground/30'
  }
}

function getStateLabel(state: InstanceState): string {
  const labels: Record<InstanceState, string> = {
    [InstanceState.OPENING]: 'Opening',
    [InstanceState.OPEN]: 'Open',
    [InstanceState.IDLE]: 'Idle',
    [InstanceState.IN_USE]: 'In Use',
    [InstanceState.CLOSING]: 'Closing',
    [InstanceState.CLOSED]: 'Closed',
    [InstanceState.ERROR]: 'Error',
    [InstanceState.CRASHED]: 'Crashed',
  }
  return labels[state]
}

export function InstancesPanel() {
  const queryClient = useQueryClient()

  const { data: instances, isLoading } = useQuery({
    queryKey: ['instances'],
    queryFn: () => api.getInstances(),
  })

  const closeMutation = useMutation({
    mutationFn: (id: string) => api.closeInstance(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['instances'] })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteInstance(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['instances'] })
    },
  })

  const activeInstances = instances?.filter((i) =>
    [InstanceState.OPEN, InstanceState.IDLE, InstanceState.IN_USE].includes(i.state)
  )

  if (isLoading) {
    return (
      <Card title="Document Instances">
        <LoadingState rows={3} />
      </Card>
    )
  }

  return (
    <Card
      title="Document Instances"
      subtitle={`${activeInstances?.length || 0} active of ${instances?.length || 0} total`}
      className="flex flex-col h-[600px]"
    >
      <div className="-mt-2 flex-1 overflow-y-auto">
        {!instances || instances.length === 0 ? (
          <EmptyState
            icon={<FileText className="w-12 h-12" />}
            message="No document instances"
            detail="Instances will appear here when documents are opened"
          />
        ) : (
          <div className="space-y-3">
            {instances.map((instance) => (
              <div
                key={instance.id}
                className={cn(
                  'border-l-[3px] bg-depth-1 rounded-lg p-4 border border-border transition-colors',
                  getBorderColor(instance.state)
                )}
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    {/* Title + Status row */}
                    <div className="flex items-center gap-2.5 mb-3">
                      <span className="font-medium text-foreground truncate">
                        {instance.document?.title || 'Standalone Instance'}
                      </span>
                      <StatusIndicator
                        status={getStatusIndicatorStatus(instance.state)}
                      />
                      <Badge variant={getBadgeVariant(instance.state)}>
                        {getStateLabel(instance.state)}
                      </Badge>
                    </div>

                    {/* Stats grid */}
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-x-6 gap-y-2">
                      <div>
                        <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
                          Driver
                        </div>
                        <div className="mt-0.5 text-sm font-mono text-foreground">
                          {instance.driverType}
                        </div>
                      </div>
                      <div>
                        <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
                          PID
                        </div>
                        <div className="mt-0.5 text-sm font-mono text-foreground">
                          {instance.processPid || '\u2014'}
                        </div>
                      </div>
                      <div>
                        <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
                          Memory
                        </div>
                        <div className="mt-0.5 text-sm font-mono text-foreground">
                          {instance.memoryMb ? `${instance.memoryMb} MB` : '\u2014'}
                        </div>
                      </div>
                      <div>
                        <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
                          Last Used
                        </div>
                        <div className="mt-0.5 text-sm font-mono text-foreground">
                          {instance.lastUsedAt ? (
                            <TimeAgo date={instance.lastUsedAt} />
                          ) : (
                            '\u2014'
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Error state message */}
                    {instance.stateMessage && (
                      <div className="mt-3 text-xs text-red-400 bg-red-500/10 px-2.5 py-1.5 rounded font-mono">
                        {instance.stateMessage}
                      </div>
                    )}
                  </div>

                  {/* Action buttons */}
                  <div className="flex items-center gap-1 shrink-0">
                    {(instance.state === InstanceState.OPEN ||
                      instance.state === InstanceState.IDLE) && (
                      <button
                        onClick={() => closeMutation.mutate(instance.id)}
                        disabled={closeMutation.isPending}
                        className="p-1.5 text-muted-foreground hover:text-amber-400 hover:bg-amber-500/10 rounded transition-colors disabled:opacity-40"
                        title="Close instance"
                      >
                        <StopCircle className="w-3.5 h-3.5" />
                      </button>
                    )}

                    {(instance.state === InstanceState.CLOSED ||
                      instance.state === InstanceState.ERROR) && (
                      <button
                        onClick={() => deleteMutation.mutate(instance.id)}
                        disabled={deleteMutation.isPending}
                        className="p-1.5 text-muted-foreground hover:text-red-400 hover:bg-red-500/10 rounded transition-colors disabled:opacity-40"
                        title="Delete instance"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </Card>
  )
}
