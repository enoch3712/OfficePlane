'use client'

import { useEffect, useState, useCallback, useRef } from 'react'
import type { WebSocketEvent } from '@/lib/types'

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8001'

type ConnectionStatus = 'connecting' | 'connected' | 'disconnected' | 'error'

export function useWebSocket() {
  const [status, setStatus] = useState<ConnectionStatus>('disconnected')
  const [events, setEvents] = useState<WebSocketEvent[]>([])
  const ws = useRef<WebSocket | null>(null)
  const reconnectTimeout = useRef<NodeJS.Timeout | undefined>(undefined)
  const reconnectAttempts = useRef(0)

  const connect = useCallback(() => {
    if (ws.current?.readyState === WebSocket.OPEN) return

    setStatus('connecting')

    try {
      const socket = new WebSocket(`${WS_URL}/ws`)

      socket.onopen = () => {
        console.log('[WS] Connected')
        setStatus('connected')
        reconnectAttempts.current = 0
      }

      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as WebSocketEvent
          setEvents((prev) => [data, ...prev].slice(0, 100)) // Keep last 100 events
        } catch (error) {
          console.error('[WS] Failed to parse message:', error)
        }
      }

      socket.onerror = () => {
        if (process.env.NODE_ENV !== 'production') {
          console.warn('[WS] Error event', { readyState: socket.readyState })
        }
      }

      socket.onclose = () => {
        console.log('[WS] Disconnected')
        setStatus('disconnected')
        ws.current = null

        // Exponential backoff reconnection
        const delay = Math.min(1000 * Math.pow(2, reconnectAttempts.current), 30000)
        reconnectAttempts.current += 1

        console.log(`[WS] Reconnecting in ${delay}ms (attempt ${reconnectAttempts.current})`)
        reconnectTimeout.current = setTimeout(connect, delay)
      }

      ws.current = socket
    } catch (error) {
      console.error('[WS] Connection failed:', error)
      setStatus('error')
    }
  }, [])

  const disconnect = useCallback(() => {
    if (reconnectTimeout.current) {
      clearTimeout(reconnectTimeout.current)
    }
    if (ws.current) {
      ws.current.close()
      ws.current = null
    }
  }, [])

  useEffect(() => {
    connect()
    return () => disconnect()
  }, [connect, disconnect])

  return {
    status,
    events,
    reconnect: connect,
    disconnect,
  }
}
