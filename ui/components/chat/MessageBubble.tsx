'use client'

import { useState } from 'react'
import type { Citation } from '@/lib/api/chat'

interface MessageBubbleProps {
  role: 'user' | 'assistant'
  content: string
  citations?: Citation[]
}

function CitationChip({ index, citation }: { index: number; citation: Citation | undefined }) {
  const [show, setShow] = useState(false)

  return (
    <span className="relative inline-block align-super">
      <button
        className="inline-flex items-center justify-center w-4 h-4 rounded-full bg-[#5EFCAB]/20 border border-[#5EFCAB]/40 text-[#5EFCAB] text-[9px] font-mono font-bold hover:bg-[#5EFCAB]/30 transition-colors cursor-pointer"
        onMouseEnter={() => setShow(true)}
        onMouseLeave={() => setShow(false)}
        onClick={() => setShow((v) => !v)}
        aria-label={`Citation ${index}`}
      >
        {index}
      </button>
      {show && citation && (
        <span className="absolute z-50 bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 p-2 rounded-lg border border-[#374151] bg-[#1C1F26] shadow-xl text-left pointer-events-none">
          <span className="block text-[10px] font-mono text-[#5EFCAB] mb-1">
            [{citation.index}] Doc {citation.document_id.slice(0, 8)}…
          </span>
          <span className="block text-xs text-[#9CA3AF] italic leading-relaxed line-clamp-4">
            {citation.text_excerpt}
          </span>
        </span>
      )}
    </span>
  )
}

function renderWithCitations(text: string, citations: Citation[]) {
  const parts: React.ReactNode[] = []
  const regex = /\[(\d+)\]/g
  let lastIndex = 0
  let match: RegExpExecArray | null

  while ((match = regex.exec(text)) !== null) {
    const idx = parseInt(match[1], 10)
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index))
    }
    const citation = citations.find((c) => c.index === idx)
    parts.push(
      <CitationChip key={`${idx}-${match.index}`} index={idx} citation={citation} />
    )
    lastIndex = match.index + match[0].length
  }
  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex))
  }
  return parts
}

export function MessageBubble({ role, content, citations = [] }: MessageBubbleProps) {
  const isUser = role === 'user'

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-3`}>
      <div
        className={`max-w-[75%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
          isUser
            ? 'bg-[#1C2030] border border-[#374151] text-[#E5E7EB] rounded-br-sm'
            : 'bg-[#0D2318] border border-[#5EFCAB]/20 text-[#D1FAE5] rounded-bl-sm'
        }`}
      >
        {isUser
          ? content
          : renderWithCitations(content, citations)}
      </div>
    </div>
  )
}
