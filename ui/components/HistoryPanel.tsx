'use client'

import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { EventType, WebSocketEvent } from '@/lib/types'
import { Activity, FileText, CheckCircle, XCircle, Play, Clock } from 'lucide-react'
import { format } from 'date-fns'
import { TimeAgo } from './TimeAgo'

interface HistoryPanelProps {
  recentEvents?: WebSocketEvent[]
}

export function HistoryPanel({ recentEvents }: HistoryPanelProps) {
  const { data: history, isLoading } = useQuery({
    queryKey: ['history'],
    queryFn: () => api.getHistory({ limit: 50 }),
  })

  const getEventIcon = (eventType: EventType) => {
    const iconMap: Record<EventType, any> = {
      // Instance events
      [EventType.INSTANCE_CREATED]: Play,
      [EventType.INSTANCE_OPENED]: FileText,
      [EventType.INSTANCE_USED]: Activity,
      [EventType.INSTANCE_CLOSED]: FileText,
      [EventType.INSTANCE_ERROR]: XCircle,
      [EventType.INSTANCE_HEARTBEAT]: Activity,

      // Task events
      [EventType.TASK_QUEUED]: Clock,
      [EventType.TASK_STARTED]: Play,
      [EventType.TASK_COMPLETED]: CheckCircle,
      [EventType.TASK_FAILED]: XCircle,
      [EventType.TASK_RETRY]: Activity,
      [EventType.TASK_CANCELLED]: XCircle,
      [EventType.TASK_TIMEOUT]: Clock,

      // Document events
      [EventType.DOCUMENT_CREATED]: FileText,
      [EventType.DOCUMENT_IMPORTED]: FileText,
      [EventType.DOCUMENT_EXPORTED]: FileText,
      [EventType.DOCUMENT_EDITED]: FileText,
      [EventType.DOCUMENT_DELETED]: XCircle,

      // System events
      [EventType.SYSTEM_STARTUP]: Play,
      [EventType.SYSTEM_SHUTDOWN]: XCircle,
      [EventType.WORKER_STARTED]: Play,
      [EventType.WORKER_STOPPED]: XCircle,
    }
    return iconMap[eventType] || Activity
  }

  const getEventColor = (eventType: EventType) => {
    if (eventType.includes('ERROR') || eventType.includes('FAILED') || eventType.includes('TIMEOUT')) {
      return 'text-error-600 bg-error-50'
    }
    if (eventType.includes('COMPLETED') || eventType.includes('OPENED')) {
      return 'text-success-600 bg-success-50'
    }
    if (eventType.includes('STARTED') || eventType.includes('RUNNING')) {
      return 'text-primary-600 bg-primary-50'
    }
    return 'text-gray-600 bg-gray-50'
  }

  if (isLoading) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-6 bg-gray-200 rounded w-48" />
          <div className="space-y-3">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="h-16 bg-gray-100 rounded" />
            ))}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-lg shadow">
      <div className="p-6 border-b border-gray-200">
        <h2 className="text-lg font-semibold text-gray-900">Execution History</h2>
        <p className="text-sm text-gray-500">Recent events and state transitions</p>
      </div>

      <div className="p-6">
        {!history || history.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-gray-400">
            <Activity className="w-16 h-16 mb-4" />
            <p className="text-sm">No execution history</p>
          </div>
        ) : (
          <div className="relative">
            {/* Timeline line */}
            <div className="absolute left-6 top-0 bottom-0 w-px bg-gray-200" />

            <div className="space-y-4">
              {history.map((event, index) => {
                const Icon = getEventIcon(event.eventType)
                const colorClass = getEventColor(event.eventType)

                return (
                  <div key={event.id} className="relative pl-14">
                    {/* Timeline dot */}
                    <div className={`absolute left-4 top-2 p-1.5 rounded-full ${colorClass}`}>
                      <Icon className="w-3 h-3" />
                    </div>

                    <div className="bg-gray-50 rounded-lg p-4 hover:bg-gray-100 transition-colors">
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="font-medium text-gray-900">
                              {event.eventType.replace(/_/g, ' ')}
                            </span>
                            {event.durationMs && (
                              <span className="text-xs text-gray-500">
                                ({event.durationMs}ms)
                              </span>
                            )}
                          </div>

                          {event.eventMessage && (
                            <p className="text-sm text-gray-700 mb-2">{event.eventMessage}</p>
                          )}

                          <div className="flex items-center gap-4 text-xs text-gray-500">
                            <div className="flex items-center gap-1">
                              <Clock className="w-3 h-3" />
                              <TimeAgo date={event.timestamp} />
                            </div>

                            {event.document && (
                              <div className="flex items-center gap-1">
                                <FileText className="w-3 h-3" />
                                {event.document.title}
                              </div>
                            )}

                            {event.task && (
                              <div>
                                Task: {event.task.taskType} ({event.task.state})
                              </div>
                            )}

                            {event.actorType && (
                              <div>
                                Actor: {event.actorType}
                                {event.actorId && ` (${event.actorId})`}
                              </div>
                            )}
                          </div>
                        </div>

                        <div className="text-xs text-gray-400">
                          {format(new Date(event.timestamp), 'HH:mm:ss')}
                        </div>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
