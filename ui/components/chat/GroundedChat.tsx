'use client'

import { useEffect, useRef, useState } from 'react'
import { ScopePicker, type ScopeState } from './ScopePicker'
import { MessageBubble } from './MessageBubble'
import { CitationCard } from './CitationCard'
import { groundedChat, type ChatMessage, type Citation } from '@/lib/api/chat'

interface Message {
  role: 'user' | 'assistant'
  content: string
  citations?: Citation[]
  mode?: 'grounded' | 'ungrounded'
  model?: string
  retrieval_count?: number
}

export function GroundedChat() {
  const [messages, setMessages] = useState<Message[]>([])
  const [scope, setScope] = useState<ScopeState>({ mode: 'all' })
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const query = input.trim()
    if (!query || loading) return

    setInput('')
    setError(null)
    setMessages((prev) => [...prev, { role: 'user', content: query }])
    setLoading(true)

    const history: ChatMessage[] = messages.map((m) => ({
      role: m.role,
      content: m.content,
    }))

    try {
      const res = await groundedChat({
        query,
        history,
        ...(scope.mode === 'document' && scope.document_ids?.length
          ? { document_ids: scope.document_ids }
          : scope.mode === 'collection' && scope.collection_id
            ? { collection_id: scope.collection_id }
            : {}),
      })

      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: res.answer,
          citations: res.citations,
          mode: res.mode,
          model: res.model,
          retrieval_count: res.retrieval_count,
        },
      ])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }

  const lastAssistant = [...messages].reverse().find((m) => m.role === 'assistant')

  return (
    <div className="flex flex-col h-full bg-[#0F1116]">
      <ScopePicker scope={scope} onChange={setScope} />

      {/* Message list */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-1">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full gap-3 text-center">
            <div className="w-10 h-10 rounded-xl bg-[#5EFCAB]/10 border border-[#5EFCAB]/20 flex items-center justify-center">
              <span className="text-[#5EFCAB] text-lg font-mono">?</span>
            </div>
            <p className="text-sm text-[#4B5563] max-w-xs">
              Ask a question about your documents. Answers are grounded in retrieved passages.
            </p>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i}>
            <MessageBubble
              role={msg.role}
              content={msg.content}
              citations={msg.citations}
            />
            {msg.role === 'assistant' && (
              <div className="pl-2 mb-1">
                {/* Mode + meta badges */}
                <div className="flex items-center gap-2 mb-1">
                  <span
                    className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-mono border ${
                      msg.mode === 'grounded'
                        ? 'bg-[#5EFCAB]/10 border-[#5EFCAB]/30 text-[#5EFCAB]'
                        : 'bg-amber-500/10 border-amber-500/30 text-amber-400'
                    }`}
                  >
                    {msg.mode === 'grounded' ? 'grounded' : 'ungrounded'}
                  </span>
                  {msg.retrieval_count !== undefined && msg.retrieval_count > 0 && (
                    <span className="text-[10px] font-mono text-[#374151]">
                      {msg.retrieval_count} passage{msg.retrieval_count !== 1 ? 's' : ''}
                    </span>
                  )}
                  {msg.model && (
                    <span className="text-[10px] font-mono text-[#374151]">
                      {msg.model.split('/').pop()}
                    </span>
                  )}
                </div>
                {/* Citation cards only for last assistant message */}
                {i === messages.length - 1 && msg.citations && msg.citations.length > 0 && (
                  <CitationCard citations={msg.citations} />
                )}
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="flex justify-start mb-3">
            <div className="max-w-[75%] rounded-2xl rounded-bl-sm px-4 py-3 bg-[#0D2318] border border-[#5EFCAB]/20">
              <div className="flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-[#5EFCAB]/60 animate-bounce [animation-delay:0ms]" />
                <span className="w-1.5 h-1.5 rounded-full bg-[#5EFCAB]/60 animate-bounce [animation-delay:150ms]" />
                <span className="w-1.5 h-1.5 rounded-full bg-[#5EFCAB]/60 animate-bounce [animation-delay:300ms]" />
              </div>
            </div>
          </div>
        )}

        {error && (
          <div className="flex justify-start mb-3">
            <div className="max-w-[75%] rounded-2xl rounded-bl-sm px-4 py-3 bg-red-950/20 border border-red-500/30 text-red-400 text-sm">
              Error: {error}
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input bar */}
      <form
        onSubmit={handleSubmit}
        className="px-4 py-3 border-t border-[#374151] bg-[#0F1116] flex items-end gap-2"
      >
        <textarea
          className="flex-1 resize-none rounded-lg border border-[#374151] bg-[#1C1F26] text-sm text-[#E5E7EB] placeholder-[#4B5563] px-3 py-2.5 focus:outline-none focus:border-[#5EFCAB]/40 transition-colors min-h-[42px] max-h-32"
          placeholder="Ask about your documents…"
          rows={1}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              handleSubmit(e as unknown as React.FormEvent)
            }
          }}
          disabled={loading}
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="flex-shrink-0 px-4 py-2.5 rounded-lg bg-[#5EFCAB]/15 border border-[#5EFCAB]/30 text-[#5EFCAB] text-sm font-mono hover:bg-[#5EFCAB]/25 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {loading ? '…' : 'Ask'}
        </button>
      </form>
    </div>
  )
}
