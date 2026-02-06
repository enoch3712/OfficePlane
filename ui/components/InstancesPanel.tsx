'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { InstanceState } from '@/lib/types'
import { FileText, StopCircle, Trash2, Clock } from 'lucide-react'
import { TimeAgo } from './TimeAgo'

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

  const getStateBadge = (state: InstanceState) => {
    const badges: Record<InstanceState, { class: string; label: string }> = {
      [InstanceState.OPENING]: { class: 'badge badge-queued', label: 'Opening' },
      [InstanceState.OPEN]: { class: 'badge badge-open', label: 'Open' },
      [InstanceState.IDLE]: { class: 'badge badge-completed', label: 'Idle' },
      [InstanceState.IN_USE]: { class: 'badge badge-running', label: 'In Use' },
      [InstanceState.CLOSING]: { class: 'badge badge-queued', label: 'Closing' },
      [InstanceState.CLOSED]: { class: 'badge badge-completed', label: 'Closed' },
      [InstanceState.ERROR]: { class: 'badge badge-failed', label: 'Error' },
      [InstanceState.CRASHED]: { class: 'badge badge-failed', label: 'Crashed' },
    }
    const badge = badges[state]
    return <span className={badge.class}>{badge.label}</span>
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
          <h2 className="text-lg font-semibold text-white">Document Instances</h2>
          <p className="text-sm text-slate-500">
            {activeInstances?.length || 0} active of {instances?.length || 0} total
          </p>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        {!instances || instances.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-slate-500">
            <FileText className="w-16 h-16 mb-4" />
            <p className="text-sm">No document instances</p>
          </div>
        ) : (
          <div className="space-y-3">
            {instances.map((instance) => (
              <div
                key={instance.id}
                className="p-4 border border-white/10 rounded-lg hover:border-[#39ff14]/30 hover:shadow-sm transition-all"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <FileText className="w-4 h-4 text-slate-400" />
                      <span className="font-medium text-white">
                        {instance.document?.title || 'Standalone Instance'}
                      </span>
                      {getStateBadge(instance.state)}
                    </div>

                    <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
                      <div className="text-slate-500">
                        Driver: <span className="text-white">{instance.driverType}</span>
                      </div>
                      <div className="text-slate-500">
                        PID: <span className="text-white">{instance.processPid || 'N/A'}</span>
                      </div>
                      {instance.lastUsedAt && (
                        <div className="text-slate-500 flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          Last used <TimeAgo date={instance.lastUsedAt} />
                        </div>
                      )}
                      {instance.memoryMb && (
                        <div className="text-slate-500">
                          Memory: <span className="text-white">{instance.memoryMb} MB</span>
                        </div>
                      )}
                    </div>

                    {instance.stateMessage && (
                      <div className="mt-2 text-xs text-red-400 bg-red-500/10 px-2 py-1 rounded">
                        {instance.stateMessage}
                      </div>
                    )}
                  </div>

                  <div className="flex items-center gap-2 ml-4">
                    {instance.state === InstanceState.OPEN ||
                    instance.state === InstanceState.IDLE ? (
                      <button
                        onClick={() => closeMutation.mutate(instance.id)}
                        disabled={closeMutation.isPending}
                        className="p-2 text-amber-400 hover:bg-amber-500/10 rounded transition-colors"
                        title="Close instance"
                      >
                        <StopCircle className="w-4 h-4" />
                      </button>
                    ) : null}

                    {instance.state === InstanceState.CLOSED ||
                    instance.state === InstanceState.ERROR ? (
                      <button
                        onClick={() => deleteMutation.mutate(instance.id)}
                        disabled={deleteMutation.isPending}
                        className="p-2 text-red-400 hover:bg-red-500/10 rounded transition-colors"
                        title="Delete instance"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    ) : null}
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
