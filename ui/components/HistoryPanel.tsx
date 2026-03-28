'use client'

import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { EventType, WebSocketEvent } from '@/lib/types'
import { Activity } from 'lucide-react'
import { format } from 'date-fns'
import { TimeAgo } from './TimeAgo'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { EmptyState } from '@/components/ui/empty-state'
import { LoadingState } from '@/components/ui/loading-state'

interface HistoryPanelProps {
  recentEvents?: WebSocketEvent[]
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

type BadgeVariant = 'error' | 'success' | 'accent' | 'warning' | 'neutral'

/** Map an EventType to a short category label shown inside the Badge. */
function getCategoryLabel(eventType: EventType): string {
  if (eventType.startsWith('INSTANCE_')) return 'INSTANCE'
  if (eventType.startsWith('TASK_')) return 'TASK'
  if (eventType.startsWith('DOCUMENT_')) return 'DOC'
  if (eventType.startsWith('SYSTEM_') || eventType.startsWith('WORKER_')) return 'SYSTEM'
  return 'EVENT'
}

/** Map an EventType to a Badge colour variant. */
function getBadgeVariant(eventType: EventType): BadgeVariant {
  if (
    eventType.includes('ERROR') ||
    eventType.includes('FAILED') ||
    eventType.includes('TIMEOUT') ||
    eventType.includes('CRASHED') ||
    eventType.includes('DELETED')
  ) {
    return 'error'
  }
  if (eventType.includes('COMPLETED') || eventType.includes('OPENED')) {
    return 'success'
  }
  if (
    eventType.includes('STARTED') ||
    eventType.includes('RUNNING') ||
    eventType.includes('USED') ||
    eventType.includes('STARTUP')
  ) {
    return 'accent'
  }
  if (eventType.includes('QUEUED') || eventType.includes('RETRY')) {
    return 'warning'
  }
  return 'neutral'
}

/** Turn TASK_COMPLETED into "Task Completed". */
function formatEventName(eventType: EventType): string {
  return eventType
    .replace(/_/g, ' ')
    .toLowerCase()
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

/** Format a millisecond duration into a readable string. */
function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`
  return `${(ms / 60_000).toFixed(1)}m`
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function HistoryPanel({ recentEvents }: HistoryPanelProps) {
  const { data: history, isLoading } = useQuery({
    queryKey: ['history'],
    queryFn: () => api.getHistory({ limit: 50 }),
  })

  if (isLoading) {
    return (
      <Card title="Recent Events">
        <LoadingState rows={6} />
      </Card>
    )
  }

  if (!history || history.length === 0) {
    return (
      <Card title="Recent Events">
        <EmptyState
          icon={<Activity className="h-10 w-10" />}
          message="No execution history"
          detail="Events will appear here as the system runs"
        />
      </Card>
    )
  }

  return (
    <Card title="Recent Events">
      {/* Left-border timeline accent line wrapping the list */}
      <div className="border-l-[3px] border-primary pl-4">
        {history.map((event) => {
          const variant = getBadgeVariant(event.eventType)
          const category = getCategoryLabel(event.eventType)
          const name = formatEventName(event.eventType)

          return (
            <div
              key={event.id}
              className="flex items-center gap-3 border-b border-border py-2.5 last:border-b-0"
            >
              {/* TimeAgo – mono, left-aligned, fixed width */}
              <TimeAgo
                date={event.timestamp}
                className="w-24 shrink-0 text-xs font-mono text-muted-foreground"
              />

              {/* Category badge */}
              <Badge variant={variant} className="shrink-0">
                {category}
              </Badge>

              {/* Event name */}
              <span className="min-w-0 flex-1 truncate text-sm font-medium text-foreground">
                {name}
              </span>

              {/* Duration (if available) */}
              {event.durationMs != null && (
                <span className="shrink-0 text-xs font-mono text-muted-foreground">
                  {formatDuration(event.durationMs)}
                </span>
              )}

              {/* Absolute timestamp – far right */}
              <span className="shrink-0 text-xs font-mono text-muted-foreground/60">
                {format(new Date(event.timestamp), 'HH:mm:ss')}
              </span>
            </div>
          )
        })}
      </div>
    </Card>
  )
}
