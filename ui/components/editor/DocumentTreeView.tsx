'use client'

import { useState } from 'react'
import { Pencil, Trash2, Check, X, Sparkles } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { InsertNodeMenu } from './InsertNodeMenu'
import { RewriteDialog } from './RewriteDialog'
import type { AgnosticDocument, DocNode, BlockType } from '@/lib/types'
import { cn } from '@/lib/cn'

interface DocumentTreeViewProps {
  document: AgnosticDocument
  workspaceId?: string
  onInsert: (
    op: 'insert_after' | 'insert_before' | 'insert_as_child',
    anchorId: string,
    node: DocNode,
  ) => Promise<void>
  onReplace: (targetId: string, node: DocNode) => Promise<void>
  onDelete: (targetId: string) => Promise<void>
  disabled?: boolean
}

// ─── Single node renderer ─────────────────────────────────────────────────────

interface NodeRowProps {
  node: DocNode
  depth: number
  workspaceId?: string
  onInsert: DocumentTreeViewProps['onInsert']
  onReplace: DocumentTreeViewProps['onReplace']
  onDelete: DocumentTreeViewProps['onDelete']
  disabled?: boolean
}

const REWRITABLE_TYPES = new Set(['paragraph', 'heading', 'callout', 'quote', 'code'])

function NodeRow({ node, depth, workspaceId, onInsert, onReplace, onDelete, disabled }: NodeRowProps) {
  const [editing, setEditing] = useState(false)
  const [editText, setEditText] = useState(node.text ?? node.heading ?? '')
  const [selected, setSelected] = useState(false)
  const [hovering, setHovering] = useState(false)
  const [busy, setBusy] = useState(false)
  const [rewriteFor, setRewriteFor] = useState<string | null>(null)

  const canRewrite = REWRITABLE_TYPES.has(node.type) && !!workspaceId

  const indentPx = depth * 16

  async function commitEdit() {
    setBusy(true)
    const updated: DocNode = { ...node, text: editText, heading: node.heading ? editText : node.heading }
    try {
      await onReplace(node.id, updated)
    } finally {
      setBusy(false)
      setEditing(false)
    }
  }

  async function handleDelete() {
    if (!confirm('Delete this block?')) return
    setBusy(true)
    try {
      await onDelete(node.id)
    } finally {
      setBusy(false)
    }
  }

  const canEdit = ['paragraph', 'heading', 'quote', 'callout', 'code'].includes(node.type)

  return (
    <div
      className={cn(
        'group relative rounded-lg transition-colors',
        selected && 'ring-1 ring-[#5EFCAB]/60',
        hovering && !editing && 'bg-white/[0.02]',
      )}
      style={{ paddingLeft: indentPx }}
      onMouseEnter={() => setHovering(true)}
      onMouseLeave={() => setHovering(false)}
      onClick={() => setSelected((v) => !v)}
    >
      <div className="py-1.5 pr-2">
        {/* Node content */}
        <NodeContent
          node={node}
          editing={editing}
          editText={editText}
          onEditText={setEditText}
          onCommit={() => void commitEdit()}
          onCancel={() => { setEditing(false); setEditText(node.text ?? node.heading ?? '') }}
          busy={busy}
        />
      </div>

      {/* Hover toolbar */}
      {hovering && !editing && !busy && (
        <div
          className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1 z-10"
          onClick={(e) => e.stopPropagation()}
        >
          {canEdit && (
            <button
              type="button"
              onClick={() => { setEditing(true); setEditText(node.text ?? node.heading ?? '') }}
              disabled={disabled}
              className="p-1 rounded text-muted-foreground hover:text-[#5EFCAB] hover:bg-[#5EFCAB]/10 transition-colors"
              title="Edit"
            >
              <Pencil className="w-3 h-3" />
            </button>
          )}
          {canRewrite && (
            <button
              type="button"
              onClick={() => setRewriteFor(node.id)}
              disabled={disabled}
              className="p-1 rounded text-muted-foreground hover:text-[#5EFCAB] hover:bg-[#5EFCAB]/10 transition-colors"
              title="Rewrite with AI"
            >
              <Sparkles className="w-3 h-3" />
            </button>
          )}
          <button
            type="button"
            onClick={() => void handleDelete()}
            disabled={disabled}
            className="p-1 rounded text-muted-foreground hover:text-red-400 hover:bg-red-400/10 transition-colors"
            title="Delete"
          >
            <Trash2 className="w-3 h-3" />
          </button>
        </div>
      )}

      {/* Rewrite Dialog */}
      {canRewrite && rewriteFor && workspaceId && (
        <RewriteDialog
          open={rewriteFor === node.id}
          onOpenChange={(open) => { if (!open) setRewriteFor(null) }}
          workspaceId={workspaceId}
          nodeId={node.id}
          currentText={node.text ?? node.heading ?? ''}
          onAccept={async (newNode) => {
            await onReplace(node.id, newNode as unknown as DocNode)
            setRewriteFor(null)
          }}
        />
      )}

      {/* Children */}
      {node.children && node.children.length > 0 && (
        <div className="mt-1">
          {node.children.map((child, idx) => (
            <div key={child.id}>
              <InsertGap
                anchorId={idx === 0 ? node.id : node.children![idx - 1].id}
                mode={idx === 0 ? 'insert_as_child' : 'insert_after'}
                onInsert={onInsert}
                disabled={disabled}
              />
              <NodeRow
                node={child}
                depth={depth + 1}
                workspaceId={workspaceId}
                onInsert={onInsert}
                onReplace={onReplace}
                onDelete={onDelete}
                disabled={disabled}
              />
            </div>
          ))}
          <InsertGap
            anchorId={node.children[node.children.length - 1].id}
            mode="insert_after"
            onInsert={onInsert}
            disabled={disabled}
          />
        </div>
      )}
    </div>
  )
}

// ─── Content renderers ─────────────────────────────────────────────────────────

interface NodeContentProps {
  node: DocNode
  editing: boolean
  editText: string
  onEditText: (v: string) => void
  onCommit: () => void
  onCancel: () => void
  busy: boolean
}

function NodeContent({ node, editing, editText, onEditText, onCommit, onCancel, busy }: NodeContentProps) {
  if (editing) {
    return (
      <div className="space-y-2" onClick={(e) => e.stopPropagation()}>
        <textarea
          autoFocus
          value={editText}
          onChange={(e) => onEditText(e.target.value)}
          rows={3}
          className="w-full px-3 py-2 bg-depth-0 border border-[#5EFCAB]/30 rounded text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-[#5EFCAB]/50 resize-none"
        />
        <div className="flex gap-2">
          <Button
            size="sm"
            onClick={onCommit}
            disabled={busy}
            className="h-7 px-3 text-xs bg-[#5EFCAB]/15 border border-[#5EFCAB]/30 text-[#5EFCAB] hover:bg-[#5EFCAB]/25"
          >
            <Check className="w-3 h-3 mr-1" />
            Save
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={onCancel}
            disabled={busy}
            className="h-7 px-3 text-xs"
          >
            <X className="w-3 h-3 mr-1" />
            Cancel
          </Button>
        </div>
      </div>
    )
  }

  switch (node.type) {
    case 'section':
      return (
        <div>
          <span
            className={cn(
              'font-heading font-semibold text-foreground',
              node.level === 1 ? 'text-lg' : node.level === 2 ? 'text-base' : 'text-sm',
            )}
          >
            {node.heading ?? `[Section ${node.id}]`}
          </span>
        </div>
      )

    case 'heading': {
      const Tag = (['h1', 'h2', 'h3', 'h4', 'h5', 'h6'] as const)[(node.level ?? 2) - 1] ?? 'h2'
      const sizeClass = node.level === 1 ? 'text-xl' : node.level === 2 ? 'text-lg' : node.level === 3 ? 'text-base' : 'text-sm'
      return <Tag className={cn('font-heading font-semibold text-foreground', sizeClass)}>{node.text}</Tag>
    }

    case 'paragraph':
      return <p className="text-sm text-foreground/90 leading-relaxed">{node.text}</p>

    case 'quote':
      return (
        <blockquote className="border-l-2 border-[#5EFCAB]/40 pl-3 text-sm italic text-muted-foreground">
          {node.text}
        </blockquote>
      )

    case 'callout':
      return (
        <div className="px-3 py-2 rounded border border-border bg-depth-2 text-sm text-foreground">
          {node.variant && (
            <span className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground mr-2">
              {node.variant}
            </span>
          )}
          {node.text}
        </div>
      )

    case 'code':
      return (
        <pre className="px-3 py-2 rounded bg-depth-0 border border-border text-xs font-mono text-foreground overflow-x-auto">
          {node.lang && (
            <span className="block text-[10px] text-muted-foreground mb-1 font-sans uppercase tracking-wider">
              {node.lang}
            </span>
          )}
          {node.text}
        </pre>
      )

    case 'figure':
      return (
        <div className="space-y-1">
          {node.src ? (
            <img
              src={node.src}
              alt={node.alt ?? node.caption ?? ''}
              className="max-w-full rounded border border-border"
            />
          ) : (
            <div className="border border-dashed border-[#5EFCAB]/30 rounded-lg p-4 text-sm text-muted-foreground bg-[#5EFCAB]/5 space-y-2">
              <p className="text-[10px] font-mono uppercase tracking-wider text-[#5EFCAB]/70">Figure placeholder</p>
              {node.prompt && <p className="italic">{node.prompt}</p>}
            </div>
          )}
          {node.caption && (
            <p className="text-[11px] text-muted-foreground text-center">{node.caption}</p>
          )}
        </div>
      )

    case 'list':
      if (node.items && node.items.length > 0) {
        const Tag = node.ordered ? 'ol' : 'ul'
        return (
          <Tag className={cn('text-sm text-foreground/90 space-y-1 pl-4', node.ordered ? 'list-decimal' : 'list-disc')}>
            {node.items.map((item) => (
              <li key={item.id}>{item.text}</li>
            ))}
          </Tag>
        )
      }
      return <p className="text-sm text-muted-foreground italic">[Empty list]</p>

    case 'table':
      if (node.headers && node.rows) {
        return (
          <div className="overflow-x-auto">
            <table className="text-xs border-collapse w-full">
              <thead>
                <tr>
                  {node.headers.map((h, i) => (
                    <th key={i} className="px-3 py-1.5 text-left border border-border bg-depth-2 text-muted-foreground font-mono uppercase tracking-wider text-[10px]">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {node.rows.map((row, ri) => (
                  <tr key={ri} className="hover:bg-depth-2/50">
                    {row.map((cell, ci) => (
                      <td key={ci} className="px-3 py-1.5 border border-border text-foreground/80">
                        {cell}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      }
      return <p className="text-sm text-muted-foreground italic">[Empty table]</p>

    case 'divider':
      return <hr className="border-border my-1" />

    default:
      return <p className="text-xs text-muted-foreground font-mono">[{(node as DocNode).type}]</p>
  }
}

// ─── Insert gap ───────────────────────────────────────────────────────────────

interface InsertGapProps {
  anchorId: string
  mode: 'insert_after' | 'insert_before' | 'insert_as_child'
  onInsert: DocumentTreeViewProps['onInsert']
  disabled?: boolean
}

function InsertGap({ anchorId, mode, onInsert, disabled }: InsertGapProps) {
  const [hovering, setHovering] = useState(false)

  return (
    <div
      className="relative flex items-center gap-2 py-0.5 group"
      onMouseEnter={() => setHovering(true)}
      onMouseLeave={() => setHovering(false)}
    >
      <div
        className={cn(
          'flex-1 h-px transition-colors',
          hovering ? 'bg-[#5EFCAB]/30' : 'bg-transparent',
        )}
      />
      <div
        className={cn(
          'transition-opacity duration-100',
          hovering ? 'opacity-100' : 'opacity-0 group-hover:opacity-100',
        )}
      >
        <InsertNodeMenu
          anchorId={anchorId}
          mode={mode}
          onInsert={onInsert}
          disabled={disabled}
        />
      </div>
      <div
        className={cn(
          'flex-1 h-px transition-colors',
          hovering ? 'bg-[#5EFCAB]/30' : 'bg-transparent',
        )}
      />
    </div>
  )
}

// ─── Public component ─────────────────────────────────────────────────────────

export function DocumentTreeView({
  document: doc,
  workspaceId,
  onInsert,
  onReplace,
  onDelete,
  disabled,
}: DocumentTreeViewProps) {
  if (!doc.children || doc.children.length === 0) {
    return (
      <div className="text-center py-12 text-muted-foreground text-sm">
        <p>No blocks yet.</p>
        <p className="text-xs mt-1 font-mono">Add a block to get started.</p>
      </div>
    )
  }

  return (
    <div className="space-y-0">
      {doc.children.map((node, idx) => (
        <div key={node.id}>
          {idx === 0 && (
            <InsertGap
              anchorId={node.id}
              mode="insert_before"
              onInsert={onInsert}
              disabled={disabled}
            />
          )}
          <NodeRow
            node={node}
            depth={0}
            workspaceId={workspaceId}
            onInsert={onInsert}
            onReplace={onReplace}
            onDelete={onDelete}
            disabled={disabled}
          />
          <InsertGap
            anchorId={node.id}
            mode="insert_after"
            onInsert={onInsert}
            disabled={disabled}
          />
        </div>
      ))}
    </div>
  )
}
