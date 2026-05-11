'use client'

import { useEffect, useState } from 'react'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001'

export type ScopeMode = 'all' | 'document' | 'collection'

export interface ScopeState {
  mode: ScopeMode
  document_ids?: string[]
  collection_id?: string
}

interface Document {
  id: string
  title: string
}

interface Collection {
  id: string
  name: string
}

interface ScopePickerProps {
  scope: ScopeState
  onChange: (scope: ScopeState) => void
}

export function ScopePicker({ scope, onChange }: ScopePickerProps) {
  const [documents, setDocuments] = useState<Document[]>([])
  const [collections, setCollections] = useState<Collection[]>([])

  useEffect(() => {
    fetch(`${API}/api/documents`)
      .then((r) => r.ok ? r.json() : [])
      .then((data) => {
        const docs = Array.isArray(data) ? data : (data.documents ?? data.items ?? [])
        setDocuments(docs)
      })
      .catch(() => {})

    fetch(`${API}/api/ecm/collections`)
      .then((r) => r.ok ? r.json() : [])
      .then((data) => {
        const cols = Array.isArray(data) ? data : (data.collections ?? data.items ?? [])
        setCollections(cols)
      })
      .catch(() => {})
  }, [])

  const btnBase =
    'px-3 py-1.5 rounded text-xs font-mono uppercase tracking-wider border transition-colors'
  const btnActive =
    'bg-[#5EFCAB]/15 border-[#5EFCAB]/40 text-[#5EFCAB]'
  const btnInactive =
    'bg-[#1C1F26] border-[#374151] text-[#6B7280] hover:border-[#5EFCAB]/30 hover:text-[#9CA3AF]'

  return (
    <div className="flex flex-wrap items-center gap-2 px-4 py-3 border-b border-[#374151] bg-[#0F1116]">
      <span className="text-[10px] font-mono uppercase tracking-widest text-[#4B5563] mr-1">
        Scope:
      </span>

      {(['all', 'document', 'collection'] as ScopeMode[]).map((m) => (
        <button
          key={m}
          onClick={() => onChange({ mode: m })}
          className={`${btnBase} ${scope.mode === m ? btnActive : btnInactive}`}
        >
          {m === 'all' ? 'All Docs' : m === 'document' ? 'Document' : 'Collection'}
        </button>
      ))}

      {scope.mode === 'document' && (
        <select
          className="ml-2 px-2 py-1 rounded text-xs border border-[#374151] bg-[#1C1F26] text-[#9CA3AF] focus:outline-none focus:border-[#5EFCAB]/40"
          value={scope.document_ids?.[0] ?? ''}
          onChange={(e) =>
            onChange({ mode: 'document', document_ids: e.target.value ? [e.target.value] : undefined })
          }
        >
          <option value="">-- pick a document --</option>
          {documents.map((d) => (
            <option key={d.id} value={d.id}>
              {d.title ?? d.id}
            </option>
          ))}
        </select>
      )}

      {scope.mode === 'collection' && (
        <select
          className="ml-2 px-2 py-1 rounded text-xs border border-[#374151] bg-[#1C1F26] text-[#9CA3AF] focus:outline-none focus:border-[#5EFCAB]/40"
          value={scope.collection_id ?? ''}
          onChange={(e) =>
            onChange({ mode: 'collection', collection_id: e.target.value || undefined })
          }
        >
          <option value="">-- pick a collection --</option>
          {collections.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name ?? c.id}
            </option>
          ))}
        </select>
      )}
    </div>
  )
}
