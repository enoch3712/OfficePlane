'use client'

import type { Citation } from '@/lib/api/chat'

interface CitationCardProps {
  citations: Citation[]
}

export function CitationCard({ citations }: CitationCardProps) {
  if (!citations.length) return null

  return (
    <div className="mt-3 rounded-lg border border-[#374151] bg-[#0F1116] overflow-hidden">
      <div className="px-3 py-2 border-b border-[#374151] flex items-center gap-2">
        <span className="text-[10px] font-mono uppercase tracking-widest text-[#4B5563]">
          Sources
        </span>
        <span className="text-[10px] font-mono text-[#374151]">
          {citations.length} passage{citations.length !== 1 ? 's' : ''}
        </span>
      </div>
      <div className="divide-y divide-[#1C1F26]">
        {citations.map((c) => (
          <div key={c.chunk_id} className="px-3 py-2 flex items-start gap-2.5">
            <span className="flex-shrink-0 inline-flex items-center justify-center w-5 h-5 rounded-full bg-[#5EFCAB]/15 border border-[#5EFCAB]/30 text-[#5EFCAB] text-[9px] font-mono font-bold mt-0.5">
              {c.index}
            </span>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-0.5">
                <span className="text-[10px] font-mono text-[#6B7280]">
                  Doc {c.document_id.slice(0, 8)}…
                </span>
                <span className="text-[10px] font-mono text-[#374151]">
                  score {(c.score * 100).toFixed(0)}%
                </span>
              </div>
              <p className="text-xs text-[#9CA3AF] italic leading-relaxed line-clamp-2">
                {c.text_excerpt}
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
