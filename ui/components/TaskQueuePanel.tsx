'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { TaskState, TaskPriority } from '@/lib/types'
import { List, XCircle, RefreshCw, Clock, AlertCircle } from 'lucide-react'
import { TimeAgo } from './TimeAgo'
import { cn } from '@/lib/cn'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { EmptyState } from '@/components/ui/empty-state'
import { LoadingState } from '@/components/ui/loading-state'
import { StatusIndicator } from '@/components/ui/status-indicator'

const borderColorByState: Record<TaskState, string> = {
  [TaskState.RUNNING]: 'border-l-primary',
  [TaskState.RETRYING]: 'border-l-primary',
  [TaskState.QUEUED]: 'border-l-amber-400',
  [TaskState.FAILED]: 'border-l-red-500',
  [TaskState.TIMEOUT]: 'border-l-red-500',
  [TaskState.COMPLETED]: 'border-l-border',
  [TaskState.CANCELLED]: 'border-l-border',
}

const badgeVariantByState: Record<TaskState, 'accent' | 'warning' | 'error' | 'neutral'> = {
  [TaskState.RUNNING]: 'accent',
  [TaskState.RETRYING]: 'accent',
  [TaskState.QUEUED]: 'warning',
  [TaskState.FAILED]: 'error',
  [TaskState.TIMEOUT]: 'error',
  [TaskState.COMPLETED]: 'neutral',
  [TaskState.CANCELLED]: 'neutral',
}

const badgeLabelByState: Record<TaskState, string> = {
  [TaskState.RUNNING]: 'Running',
  [TaskState.RETRYING]: 'Retrying',
  [TaskState.QUEUED]: 'Queued',
  [TaskState.FAILED]: 'Failed',
  [TaskState.TIMEOUT]: 'Timeout',
  [TaskState.COMPLETED]: 'Completed',
  [TaskState.CANCELLED]: 'Cancelled',
}

const statusIndicatorByState: Record<TaskState, 'active' | 'warning' | 'error' | 'completed' | 'pending'> = {
  [TaskState.RUNNING]: 'active',
  [TaskState.RETRYING]: 'active',
  [TaskState.QUEUED]: 'warning',
  [TaskState.FAILED]: 'error',
  [TaskState.TIMEOUT]: 'error',
  [TaskState.COMPLETED]: 'completed',
  [TaskState.CANCELLED]: 'pending',
}

export function TaskQueuePanel() {
  const queryClient = useQueryClient()

  const { data: tasks, isLoading } = useQuery({
    queryKey: ['tasks'],
    queryFn: () => api.getTasks({ limit: 100 }),
  })

  const cancelMutation = useMutation({
    mutationFn: (id: string) => api.cancelTask(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] })
    },
  })

  const retryMutation = useMutation({
    mutationFn: (id: string) => api.retryTask(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] })
    },
  })

  const activeTasks = tasks?.filter((t) =>
    [TaskState.QUEUED, TaskState.RUNNING, TaskState.RETRYING].includes(t.state)
  )

  if (isLoading) {
    return (
      <Card title="Task Queue">
        <LoadingState rows={3} />
      </Card>
    )
  }

  return (
    <Card
      title="Task Queue"
      subtitle={`${activeTasks?.length || 0} active of ${tasks?.length || 0} total`}
      className="flex flex-col h-[600px]"
    >
      <div className="flex-1 overflow-y-auto -mx-5 px-5">
        {!tasks || tasks.length === 0 ? (
          <EmptyState
            icon={<List className="w-12 h-12" />}
            message="No tasks in queue"
            detail="Tasks will appear here when queued"
            className="h-full"
          />
        ) : (
          <div className="space-y-2">
            {tasks.map((task) => (
              <div
                key={task.id}
                className={cn(
                  'border-l-[3px] bg-depth-1 rounded-lg p-4 transition-colors',
                  borderColorByState[task.state]
                )}
              >
                {/* Header: name + badge */}
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-2 min-w-0">
                    <StatusIndicator status={statusIndicatorByState[task.state]} />
                    <span className="font-heading font-medium italic text-sm text-foreground truncate">
                      {task.taskName || task.taskType}
                    </span>
                    {task.priority !== TaskPriority.NORMAL && (
                      <Badge variant="info">{task.priority}</Badge>
                    )}
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    <Badge variant={badgeVariantByState[task.state]}>
                      {badgeLabelByState[task.state]}
                    </Badge>

                    {task.state === TaskState.FAILED && task.retryCount < task.maxRetries && (
                      <button
                        onClick={() => retryMutation.mutate(task.id)}
                        disabled={retryMutation.isPending}
                        className="p-1.5 text-primary hover:bg-primary/10 rounded transition-colors disabled:opacity-50"
                        title="Retry task"
                      >
                        <RefreshCw className="w-3.5 h-3.5" />
                      </button>
                    )}

                    {(task.state === TaskState.QUEUED || task.state === TaskState.RUNNING) && (
                      <button
                        onClick={() => cancelMutation.mutate(task.id)}
                        disabled={cancelMutation.isPending}
                        className="p-1.5 text-red-400 hover:bg-red-500/10 rounded transition-colors disabled:opacity-50"
                        title="Cancel task"
                      >
                        <XCircle className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                </div>

                {/* Type */}
                <div className="mt-1.5 font-mono text-xs text-muted-foreground">
                  {task.taskType}
                </div>

                {/* Document title */}
                {task.document && (
                  <div className="mt-1 text-xs text-muted-foreground">
                    Document: <span className="text-foreground">{task.document.title}</span>
                  </div>
                )}

                {/* Metadata row */}
                <div className="mt-2 flex items-center gap-4 text-xs font-mono text-muted-foreground">
                  <span className="inline-flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    <TimeAgo date={task.createdAt} />
                  </span>

                  {task.retryCount > 0 && (
                    <span className="inline-flex items-center gap-1 text-amber-400">
                      <AlertCircle className="w-3 h-3" />
                      Retry {task.retryCount}/{task.maxRetries}
                    </span>
                  )}

                  {task.startedAt && (
                    <span>
                      Started <TimeAgo date={task.startedAt} />
                    </span>
                  )}
                </div>

                {/* Error message */}
                {task.errorMessage && (
                  <div className="mt-2">
                    <Badge variant="error" className="text-[10px] normal-case tracking-normal max-w-full">
                      <span className="truncate">{task.errorMessage}</span>
                    </Badge>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </Card>
  )
}
