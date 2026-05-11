'use client'

import { useEffect, useState } from 'react'
import { fetchDiff, DiffResponse, DiffEntry } from '@/lib/api/diff'

interface DiffViewProps {
  workspaceId: string
  from: number
  to: number
}

function nodeLabel(entry: DiffEntry): string {
  const data = entry.node || entry.after || entry.before || {}
  switch (entry.type) {
    case 'paragraph':
      return String(data.text || '').slice(0, 80) || '(empty)'
    case 'section':
      return String(data.heading || data.title || '').slice(0, 80) || '(section)'
    case 'table': {
      const headers = data.headers as string[] | undefined
      return headers ? headers.slice(0, 3).join(', ') : '(table)'
    }
    case 'figure':
      return String(data.caption || '').slice(0, 80) || '(figure)'
    default:
      return entry.type || '(node)'
  }
}

function AddedSection({ entries }: { entries: DiffEntry[] }) {
  if (!entries.length) return null
  return (
    <div className="flex-1 min-w-0">
      <h3 className="text-xs font-mono uppercase tracking-wider text-[#5EFCAB] mb-2 flex items-center gap-1">
        <span className="w-4 h-4 inline-flex items-center justify-center rounded bg-[#5EFCAB]/20 text-[#5EFCAB] font-bold text-[10px]">+</span>
        Added ({entries.length})
      </h3>
      <ul className="space-y-1.5">
        {entries.map((e) => (
          <li
            key={e.id}
            className="rounded px-3 py-2 bg-[#5EFCAB]/10 border border-[#5EFCAB]/20 text-xs"
          >
            <span className="font-mono text-[#5EFCAB] mr-2 text-[10px]">{e.type}</span>
            <span className="text-foreground/80">{nodeLabel(e)}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

function RemovedSection({ entries }: { entries: DiffEntry[] }) {
  if (!entries.length) return null
  return (
    <div className="flex-1 min-w-0">
      <h3 className="text-xs font-mono uppercase tracking-wider text-red-400 mb-2 flex items-center gap-1">
        <span className="w-4 h-4 inline-flex items-center justify-center rounded bg-red-500/20 text-red-400 font-bold text-[10px]">−</span>
        Removed ({entries.length})
      </h3>
      <ul className="space-y-1.5">
        {entries.map((e) => (
          <li
            key={e.id}
            className="rounded px-3 py-2 bg-red-500/10 border border-red-500/20 text-xs line-through decoration-red-400/60"
          >
            <span className="font-mono text-red-400 mr-2 text-[10px] no-underline">{e.type}</span>
            <span className="text-foreground/50">{nodeLabel(e)}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

function ChangedSection({ entries }: { entries: DiffEntry[] }) {
  if (!entries.length) return null
  return (
    <div className="flex-1 min-w-0">
      <h3 className="text-xs font-mono uppercase tracking-wider text-amber-400 mb-2 flex items-center gap-1">
        <span className="w-4 h-4 inline-flex items-center justify-center rounded bg-amber-500/20 text-amber-400 font-bold text-[10px]">~</span>
        Changed ({entries.length})
      </h3>
      <ul className="space-y-2">
        {entries.map((e) => {
          const beforeText = String((e.before as Record<string, unknown>)?.text || (e.before as Record<string, unknown>)?.heading || '').slice(0, 120)
          const afterText = String((e.after as Record<string, unknown>)?.text || (e.after as Record<string, unknown>)?.heading || '').slice(0, 120)
          return (
            <li
              key={e.id}
              className="rounded px-3 py-2 bg-amber-500/10 border border-amber-500/20 text-xs space-y-1"
            >
              <span className="font-mono text-amber-400 text-[10px]">{e.type} · {e.id}</span>
              {beforeText && (
                <p className="text-foreground/40 line-through decoration-foreground/30">
                  {beforeText}
                </p>
              )}
              {afterText && (
                <p className="text-foreground/80">{afterText}</p>
              )}
            </li>
          )
        })}
      </ul>
    </div>
  )
}

export function DiffView({ workspaceId, from, to }: DiffViewProps) {
  const [data, setData] = useState<DiffResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    setError(null)
    fetchDiff(workspaceId, from, to)
      .then(setData)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : 'Unknown error'))
      .finally(() => setLoading(false))
  }, [workspaceId, from, to])

  if (loading) {
    return (
      <div className="flex items-center gap-3 text-muted-foreground text-sm py-8">
        <div className="w-4 h-4 border-2 border-[#5EFCAB]/30 border-t-[#5EFCAB] rounded-full animate-spin" />
        Computing diff…
      </div>
    )
  }

  if (error) {
    return (
      <p className="text-sm text-red-400 py-4">Error: {error}</p>
    )
  }

  if (!data) return null

  const { summary } = data.diff
  const totalChanges = summary.added_count + summary.removed_count + summary.changed_count

  return (
    <div className="space-y-6">
      {/* Summary bar */}
      <div className="flex items-center gap-4 text-xs font-mono text-muted-foreground border-b border-border pb-4">
        <span className="text-[#5EFCAB]">+{summary.added_count} added</span>
        <span className="text-red-400">−{summary.removed_count} removed</span>
        <span className="text-amber-400">~{summary.changed_count} changed</span>
        <span className="ml-auto">
          rev {data.from_revision} ({data.from_op}) → rev {data.to_revision} ({data.to_op})
        </span>
      </div>

      {totalChanges === 0 ? (
        <p className="text-sm text-muted-foreground text-center py-8">No changes between these revisions.</p>
      ) : (
        <div className="flex gap-6 flex-wrap">
          <AddedSection entries={data.diff.added} />
          <ChangedSection entries={data.diff.changed} />
          <RemovedSection entries={data.diff.removed} />
        </div>
      )}
    </div>
  )
}
