'use client'

import { memo } from 'react'
import { Handle, Position, type NodeProps } from 'reactflow'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/cn'

export interface NodeBadgeData {
  label: string
  nodeType: string
  confidence?: number
  column: 'source' | 'generated' | 'revision'
  isSelected?: boolean
  isDimmed?: boolean
  /** For revision nodes */
  op?: string
  revisionNumber?: number
  actor?: string | null
}

const TYPE_STYLES: Record<string, { bg: string; border: string; label: string }> = {
  section: {
    bg: 'bg-[#5EFCAB]/10',
    border: 'border-[#5EFCAB]/40',
    label: 'SEC',
  },
  paragraph: {
    bg: 'bg-[#374151]/60',
    border: 'border-[#4B5563]',
    label: 'P',
  },
  heading: {
    bg: 'bg-[#5EFCAB]/15',
    border: 'border-[#5EFCAB]/50',
    label: 'H',
  },
  table: {
    bg: 'bg-blue-900/40',
    border: 'border-blue-600/40',
    label: 'TBL',
  },
  figure: {
    bg: 'bg-amber-900/40',
    border: 'border-amber-600/40',
    label: 'FIG',
  },
  // source column types
  document: {
    bg: 'bg-[#5EFCAB]/8',
    border: 'border-[#5EFCAB]/30',
    label: 'DOC',
  },
  chapter: {
    bg: 'bg-[#374151]/50',
    border: 'border-[#4B5563]',
    label: 'CH',
  },
  source_section: {
    bg: 'bg-[#374151]/40',
    border: 'border-[#4B5563]',
    label: 'S',
  },
  // revision types
  revision: {
    bg: 'bg-[#1F2937]/80',
    border: 'border-[#374151]',
    label: 'REV',
  },
}

const OP_COLORS: Record<string, string> = {
  create: 'text-[#5EFCAB]',
  insert_after: 'text-blue-400',
  replace: 'text-amber-400',
  delete: 'text-red-400',
}

function NodeBadgeInner({ data }: NodeProps<NodeBadgeData>) {
  const style = TYPE_STYLES[data.nodeType] ?? TYPE_STYLES['paragraph']
  const opColor = data.op ? (OP_COLORS[data.op] ?? 'text-muted-foreground') : null

  return (
    <div
      className={cn(
        'relative px-3 py-2 rounded-lg border text-xs min-w-[140px] max-w-[200px] transition-all duration-150',
        style.bg,
        style.border,
        data.isSelected && 'ring-1 ring-[#5EFCAB] shadow-[0_0_8px_rgba(94,252,171,0.3)]',
        data.isDimmed && 'opacity-20',
      )}
    >
      {/* Handles — all nodes get source + target handles; react-flow hides them visually */}
      <Handle
        type="target"
        position={Position.Left}
        className="!bg-[#4B5563] !w-2 !h-2 !border-0"
      />
      <Handle
        type="source"
        position={Position.Right}
        className="!bg-[#4B5563] !w-2 !h-2 !border-0"
      />

      <div className="flex items-start gap-2">
        <span className="text-[9px] font-mono uppercase tracking-wider text-muted-foreground opacity-70 mt-0.5 shrink-0">
          {style.label}
        </span>
        <div className="flex-1 min-w-0">
          {/* Revision-specific header */}
          {data.column === 'revision' && data.revisionNumber !== undefined && (
            <div className={cn('text-[10px] font-mono font-semibold mb-0.5', opColor)}>
              #{data.revisionNumber} {data.op}
            </div>
          )}
          <div className="truncate text-foreground font-medium leading-snug">
            {data.label}
          </div>
          {data.column === 'revision' && data.actor && (
            <div className="text-[9px] text-muted-foreground mt-0.5 truncate">
              {data.actor}
            </div>
          )}
        </div>
      </div>

      {/* Confidence badge for generated nodes */}
      {data.confidence !== undefined && data.column === 'generated' && (
        <div className="absolute -top-2 -right-2">
          <Badge
            variant={data.confidence >= 0.85 ? 'accent' : 'warning'}
            className="text-[9px] px-1 py-0"
          >
            {data.confidence.toFixed(2)}
          </Badge>
        </div>
      )}
    </div>
  )
}

export const NodeBadge = memo(NodeBadgeInner)
NodeBadge.displayName = 'NodeBadge'
