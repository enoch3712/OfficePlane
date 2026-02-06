'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { TaskState, TaskPriority } from '@/lib/types'
import { List, XCircle, RefreshCw, Clock, AlertCircle } from 'lucide-react'
import { TimeAgo } from './TimeAgo'

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

  const getStateBadge = (state: TaskState) => {
    const badges: Record<TaskState, { class: string; label: string }> = {
      [TaskState.QUEUED]: { class: 'badge badge-queued', label: 'Queued' },
      [TaskState.RUNNING]: { class: 'badge badge-running', label: 'Running' },
      [TaskState.COMPLETED]: { class: 'badge badge-completed', label: 'Completed' },
      [TaskState.FAILED]: { class: 'badge badge-failed', label: 'Failed' },
      [TaskState.CANCELLED]: { class: 'badge badge-completed', label: 'Cancelled' },
      [TaskState.RETRYING]: { class: 'badge badge-queued', label: 'Retrying' },
      [TaskState.TIMEOUT]: { class: 'badge badge-failed', label: 'Timeout' },
    }
    const badge = badges[state]
    return <span className={badge.class}>{badge.label}</span>
  }

  const getPriorityIndicator = (priority: TaskPriority) => {
    const colors: Record<TaskPriority, string> = {
      [TaskPriority.LOW]: 'bg-slate-500',
      [TaskPriority.NORMAL]: 'bg-blue-500',
      [TaskPriority.HIGH]: 'bg-[#39ff14]',
      [TaskPriority.CRITICAL]: 'bg-red-500',
    }
    return <div className={`w-1 h-full ${colors[priority]} rounded-l`} />
  }

  if (isLoading) {
    return (
      <div className="bg-white/[0.02] rounded-lg shadow p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-6 bg-white/10 rounded w-48" />
          <div className="space-y-3">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="h-20 bg-white/5 rounded" />
            ))}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-white/[0.02] rounded-lg shadow flex flex-col h-[600px]">
      <div className="p-6 border-b border-white/10">
        <div>
          <h2 className="text-lg font-semibold text-white">Task Queue</h2>
          <p className="text-sm text-slate-500">
            {activeTasks?.length || 0} active of {tasks?.length || 0} total
          </p>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        {!tasks || tasks.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-slate-500">
            <List className="w-16 h-16 mb-4" />
            <p className="text-sm">No tasks in queue</p>
          </div>
        ) : (
          <div className="space-y-3">
            {tasks.map((task) => (
              <div
                key={task.id}
                className="relative border border-white/10 rounded-lg hover:border-[#39ff14]/30 hover:shadow-sm transition-all overflow-hidden"
              >
                {getPriorityIndicator(task.priority)}

                <div className="p-4 pl-5">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2">
                        <List className="w-4 h-4 text-slate-400" />
                        <span className="font-medium text-white">
                          {task.taskName || task.taskType}
                        </span>
                        {getStateBadge(task.state)}
                        {task.priority !== TaskPriority.NORMAL && (
                          <span className="text-xs px-2 py-0.5 bg-white/5 text-slate-400 rounded">
                            {task.priority}
                          </span>
                        )}
                      </div>

                      <div className="space-y-1 text-sm">
                        <div className="text-slate-500">
                          Type: <span className="text-white font-mono text-xs">{task.taskType}</span>
                        </div>

                        {task.document && (
                          <div className="text-slate-500">
                            Document: <span className="text-white">{task.document.title}</span>
                          </div>
                        )}

                        <div className="flex items-center gap-4 text-xs text-slate-500">
                          <div className="flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            Created <TimeAgo date={task.createdAt} />
                          </div>

                          {task.retryCount > 0 && (
                            <div className="flex items-center gap-1 text-amber-400">
                              <AlertCircle className="w-3 h-3" />
                              Retry {task.retryCount}/{task.maxRetries}
                            </div>
                          )}

                          {task.startedAt && (
                            <div>
                              Started <TimeAgo date={task.startedAt} />
                            </div>
                          )}
                        </div>
                      </div>

                      {task.errorMessage && (
                        <div className="mt-2 text-xs text-red-400 bg-red-500/10 px-2 py-1 rounded">
                          {task.errorMessage}
                        </div>
                      )}
                    </div>

                    <div className="flex items-center gap-2 ml-4">
                      {task.state === TaskState.FAILED && task.retryCount < task.maxRetries && (
                        <button
                          onClick={() => retryMutation.mutate(task.id)}
                          disabled={retryMutation.isPending}
                          className="p-2 text-[#39ff14] hover:bg-[#39ff14]/10 rounded transition-colors"
                          title="Retry task"
                        >
                          <RefreshCw className="w-4 h-4" />
                        </button>
                      )}

                      {(task.state === TaskState.QUEUED || task.state === TaskState.RUNNING) && (
                        <button
                          onClick={() => cancelMutation.mutate(task.id)}
                          disabled={cancelMutation.isPending}
                          className="p-2 text-red-400 hover:bg-red-500/10 rounded transition-colors"
                          title="Cancel task"
                        >
                          <XCircle className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
