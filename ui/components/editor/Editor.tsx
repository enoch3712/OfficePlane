'use client'

import { useEffect, useState } from 'react'
import { RefreshCw } from 'lucide-react'
import { AgnosticDocument, DocNode } from '@/lib/types'
import { applyEdit } from '@/lib/api/documents'
import { DocumentTreeView } from './DocumentTreeView'
import { GeneratePptxDialog } from './GeneratePptxDialog'
import { Button } from '@/components/ui/button'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001'

interface EditorProps {
  workspaceId: string
}

export function Editor({ workspaceId }: EditorProps) {
  const [doc, setDoc] = useState<AgnosticDocument | null>(null)
  const [busy, setBusy] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)

  async function refresh() {
    setLoadError(null)
    try {
      const r = await fetch(`${API}/api/workspaces/${workspaceId}/document`)
      if (r.ok) {
        setDoc(await r.json())
      } else {
        setLoadError(`Failed to load document (${r.status})`)
      }
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : 'Network error')
    }
  }

  useEffect(() => {
    void refresh()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspaceId])

  async function doEdit(op: string, body: Record<string, unknown>) {
    setBusy(true)
    try {
      await applyEdit({
        workspace_id: workspaceId,
        operation: op as Parameters<typeof applyEdit>[0]['operation'],
        ...body,
      })
      await refresh()
    } finally {
      setBusy(false)
    }
  }

  if (loadError) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3 p-6">
        <p className="text-sm text-red-400">{loadError}</p>
        <Button size="sm" variant="ghost" onClick={() => void refresh()}>
          Retry
        </Button>
      </div>
    )
  }

  if (!doc) {
    return (
      <div className="flex items-center justify-center h-full gap-3 p-6 text-muted-foreground">
        <div className="w-4 h-4 border-2 border-[#5EFCAB]/30 border-t-[#5EFCAB] rounded-full animate-spin" />
        <span className="text-sm font-mono">Loading document...</span>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-[1fr_280px] h-full">
      {/* Main content area */}
      <div className="overflow-auto p-6 border-r border-border">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-xl font-semibold tracking-tight">{doc.meta.title}</h2>
          <div className="flex items-center gap-2">
            {doc.revision !== undefined && (
              <span className="text-[10px] font-mono text-muted-foreground">
                rev {doc.revision}
              </span>
            )}
            <button
              type="button"
              onClick={() => void refresh()}
              disabled={busy}
              className="p-1.5 rounded text-muted-foreground hover:text-foreground hover:bg-white/5 transition-colors disabled:opacity-40"
              title="Refresh"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${busy ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>

        <DocumentTreeView
          document={doc}
          disabled={busy}
          onInsert={(op, anchor, node) =>
            doEdit(
              op,
              op === 'insert_as_child'
                ? { parent_id: anchor, node: node as unknown as Record<string, unknown> }
                : { anchor_id: anchor, node: node as unknown as Record<string, unknown> },
            )
          }
          onReplace={(tid, node) =>
            doEdit('replace', {
              target_id: tid,
              node: node as unknown as Record<string, unknown>,
            })
          }
          onDelete={(tid) => doEdit('delete', { target_id: tid })}
        />
      </div>

      {/* Sidebar actions */}
      <aside className="p-4 flex flex-col gap-3 overflow-auto">
        <h3 className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
          Actions
        </h3>

        <GeneratePptxDialog workspaceId={workspaceId} />

        <Button variant="ghost" disabled={busy} className="w-full justify-start text-sm">
          Re-render Word
        </Button>

        <a
          className="text-sm text-primary underline hover:no-underline"
          href={`/lineage/${workspaceId}`}
        >
          View source trail
        </a>

        {doc.revision !== undefined && doc.revision > 1 && (
          <a
            className="text-sm text-primary underline hover:no-underline"
            href={`/workspaces/${workspaceId}/diff/${doc.revision - 1}/${doc.revision}`}
          >
            View changes
          </a>
        )}

        <div className="mt-auto pt-4 border-t border-border">
          <p className="text-[10px] font-mono text-muted-foreground mb-1">Workspace</p>
          <p className="text-[10px] font-mono text-muted-foreground break-all">{workspaceId}</p>
        </div>
      </aside>
    </div>
  )
}
