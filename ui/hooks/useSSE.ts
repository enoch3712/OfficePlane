'use client'

import { useEffect, useRef, useState, useCallback } from 'react'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001'

export interface SSEEvent {
  event: string
  data: Record<string, unknown>
}

type SSEStatus = 'idle' | 'connecting' | 'connected' | 'closed' | 'error'

interface UseSSEOptions {
  onEvent?: (event: SSEEvent) => void
  autoConnect?: boolean
}

export function useSSE(streamUrl: string | null, options: UseSSEOptions = {}) {
  const { onEvent, autoConnect = true } = options
  const [status, setStatus] = useState<SSEStatus>('idle')
  const [events, setEvents] = useState<SSEEvent[]>([])
  const eventSourceRef = useRef<EventSource | null>(null)
  const onEventRef = useRef(onEvent)
  onEventRef.current = onEvent

  const connect = useCallback(() => {
    if (!streamUrl) return
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
    }

    setStatus('connecting')
    const url = streamUrl.startsWith('http') ? streamUrl : `${API_URL}${streamUrl}`
    const es = new EventSource(url)
    eventSourceRef.current = es

    es.onopen = () => {
      setStatus('connected')
    }

    es.onerror = () => {
      setStatus('error')
      es.close()
      eventSourceRef.current = null
    }

    // Listen for known event types (generate + agent team events)
    const eventTypes = [
      'start', 'delta', 'tool_call', 'tool_result', 'file', 'stop', 'error',
      'team_started', 'decomposing', 'tasks_created', 'teammates_started',
      'task_claimed', 'task_completed', 'task_failed', 'synthesizing', 'team_completed', 'team_failed',
    ]
    for (const type of eventTypes) {
      es.addEventListener(type, (e: MessageEvent) => {
        try {
          const data = JSON.parse(e.data)
          const sseEvent: SSEEvent = { event: type, data }
          setEvents((prev) => [...prev, sseEvent])
          onEventRef.current?.(sseEvent)

          if (type === 'stop' || type === 'error' || type === 'team_completed' || type === 'team_failed') {
            setStatus('closed')
            es.close()
            eventSourceRef.current = null
          }
        } catch (err) {
          console.error('[SSE] Failed to parse event:', err)
        }
      })
    }
  }, [streamUrl])

  const disconnect = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }
    setStatus('idle')
  }, [])

  const reset = useCallback(() => {
    disconnect()
    setEvents([])
  }, [disconnect])

  useEffect(() => {
    if (autoConnect && streamUrl) {
      connect()
    }
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
        eventSourceRef.current = null
      }
    }
  }, [autoConnect, streamUrl, connect])

  return {
    status,
    events,
    connect,
    disconnect,
    reset,
  }
}
