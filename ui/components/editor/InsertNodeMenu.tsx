'use client'

import { useState } from 'react'
import { Plus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import type { BlockType, DocNode } from '@/lib/types'
import { cn } from '@/lib/cn'

interface InsertNodeMenuProps {
  anchorId: string
  mode: 'insert_after' | 'insert_before' | 'insert_as_child'
  onInsert: (
    op: 'insert_after' | 'insert_before' | 'insert_as_child',
    anchorId: string,
    node: DocNode,
  ) => Promise<void>
  disabled?: boolean
}

const BLOCK_TYPES: { type: BlockType; label: string; hasPrompt?: boolean }[] = [
  { type: 'paragraph', label: 'Paragraph' },
  { type: 'heading', label: 'Heading' },
  { type: 'figure', label: 'Figure', hasPrompt: true },
  { type: 'list', label: 'List' },
  { type: 'code', label: 'Code' },
  { type: 'quote', label: 'Quote' },
  { type: 'divider', label: 'Divider' },
]

function generateId(): string {
  return `node-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`
}

export function InsertNodeMenu({ anchorId, mode, onInsert, disabled }: InsertNodeMenuProps) {
  const [open, setOpen] = useState(false)
  const [pickedType, setPickedType] = useState<BlockType | null>(null)
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)

  function handlePickType(t: BlockType) {
    if (t === 'divider') {
      // No input needed — insert immediately
      void handleInsert(t, '')
      return
    }
    setPickedType(t)
    setText('')
  }

  async function handleInsert(type: BlockType, value: string) {
    setBusy(true)
    const node: DocNode = buildNode(type, value)
    try {
      await onInsert(mode, anchorId, node)
    } finally {
      setBusy(false)
      setOpen(false)
      setPickedType(null)
      setText('')
    }
  }

  function buildNode(type: BlockType, value: string): DocNode {
    const id = generateId()
    switch (type) {
      case 'paragraph':
        return { id, type: 'paragraph', text: value }
      case 'heading':
        return { id, type: 'heading', text: value, level: 2 }
      case 'figure':
        return { id, type: 'figure', prompt: value, caption: '' }
      case 'list':
        return {
          id,
          type: 'list',
          ordered: false,
          items: value
            .split('\n')
            .filter(Boolean)
            .map((t, i) => ({ id: `${id}-item-${i}`, type: 'paragraph' as BlockType, text: t })),
        }
      case 'code':
        return { id, type: 'code', text: value, lang: '' }
      case 'quote':
        return { id, type: 'quote', text: value }
      case 'divider':
        return { id, type: 'divider' }
      default:
        return { id, type: 'paragraph', text: value }
    }
  }

  const inputLabel: Record<string, string> = {
    paragraph: 'Paragraph text',
    heading: 'Heading text',
    figure: 'Image generation prompt',
    list: 'List items (one per line)',
    code: 'Code content',
    quote: 'Quote text',
  }

  return (
    <>
      <button
        type="button"
        onClick={() => { setOpen(true); setPickedType(null); setText('') }}
        disabled={disabled}
        className={cn(
          'flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono uppercase tracking-wider',
          'border border-dashed border-border text-muted-foreground',
          'hover:border-[#5EFCAB]/50 hover:text-[#5EFCAB] transition-colors',
          'disabled:opacity-40 disabled:cursor-not-allowed',
        )}
      >
        <Plus className="w-3 h-3" />
        Insert
      </button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Insert block</DialogTitle>
          </DialogHeader>

          {!pickedType ? (
            <div className="grid grid-cols-2 gap-2">
              {BLOCK_TYPES.map((bt) => (
                <button
                  key={bt.type}
                  type="button"
                  onClick={() => handlePickType(bt.type)}
                  disabled={busy}
                  className={cn(
                    'px-3 py-2 rounded border border-border text-sm text-left',
                    'hover:border-[#5EFCAB]/40 hover:bg-[#5EFCAB]/5 hover:text-[#5EFCAB]',
                    'transition-colors disabled:opacity-40',
                  )}
                >
                  {bt.label}
                </button>
              ))}
            </div>
          ) : (
            <div className="space-y-3">
              <label className="block text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
                {inputLabel[pickedType] ?? 'Content'}
              </label>
              <textarea
                autoFocus
                value={text}
                onChange={(e) => setText(e.target.value)}
                rows={pickedType === 'list' ? 4 : 3}
                className="w-full px-3 py-2 bg-depth-0 border border-border rounded-lg text-sm text-foreground placeholder-muted-foreground focus:outline-none focus:ring-1 focus:ring-[#5EFCAB]/30 resize-none"
                placeholder={pickedType === 'list' ? 'Item 1\nItem 2\nItem 3' : ''}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey && pickedType !== 'list') {
                    e.preventDefault()
                    void handleInsert(pickedType, text)
                  }
                }}
              />
              <DialogFooter>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setPickedType(null)}
                  disabled={busy}
                >
                  Back
                </Button>
                <Button
                  size="sm"
                  onClick={() => void handleInsert(pickedType, text)}
                  disabled={busy || (!text.trim() && pickedType !== 'divider')}
                  className="bg-[#5EFCAB]/15 border border-[#5EFCAB]/30 text-[#5EFCAB] hover:bg-[#5EFCAB]/25"
                >
                  Insert
                </Button>
              </DialogFooter>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </>
  )
}
