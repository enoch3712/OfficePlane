'use client'

import { useState } from 'react'
import { Loader2, Presentation } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import { generatePptx } from '@/lib/api/documents'
import { useToast } from '@/components/ui/toast'
import { cn } from '@/lib/cn'

interface GeneratePptxDialogProps {
  workspaceId: string
}

const STYLES = ['professional', 'clinical', 'corporate', 'casual', 'academic'] as const
const TONES = ['neutral', 'warm', 'authoritative', 'concise'] as const

export function GeneratePptxDialog({ workspaceId }: GeneratePptxDialogProps) {
  const [open, setOpen] = useState(false)
  const [brief, setBrief] = useState('')
  const [slideCount, setSlideCount] = useState(10)
  const [style, setStyle] = useState<string>('professional')
  const [audience, setAudience] = useState('')
  const [tone, setTone] = useState<string>('neutral')
  const [busy, setBusy] = useState(false)
  const { addToast } = useToast()

  async function handleGenerate() {
    if (!brief.trim()) return
    setBusy(true)
    try {
      const result = await generatePptx({
        source_document_ids: [workspaceId],
        brief: brief.trim(),
        slide_count: slideCount,
        style,
        audience: audience.trim() || undefined,
        tone,
      })
      addToast({
        type: 'success',
        title: 'Deck generated',
        description: result.title,
        details: [
          { label: 'Slides', value: result.slide_count },
          { label: 'Model', value: result.model },
        ],
        duration: 0,
      })
      setOpen(false)
      setBrief('')
    } catch (err) {
      addToast({
        type: 'error',
        title: 'Generation failed',
        description: err instanceof Error ? err.message : 'Unknown error',
      })
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className={cn(
          'w-full flex items-center gap-2 px-3 py-2 rounded border',
          'border-[#5EFCAB]/30 bg-[#5EFCAB]/5 text-[#5EFCAB] text-sm font-medium',
          'hover:bg-[#5EFCAB]/15 transition-colors',
        )}
      >
        <Presentation className="w-4 h-4" />
        Generate deck
      </button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Generate presentation deck</DialogTitle>
          </DialogHeader>

          <div className="space-y-4">
            {/* Brief */}
            <div>
              <label className="block text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-1.5">
                Brief
              </label>
              <textarea
                value={brief}
                onChange={(e) => setBrief(e.target.value)}
                rows={3}
                placeholder="Summarize the key findings for a clinical audience..."
                className="w-full px-3 py-2 bg-depth-0 border border-border rounded-lg text-sm text-foreground placeholder-muted-foreground focus:outline-none focus:ring-1 focus:ring-[#5EFCAB]/30 resize-none"
              />
            </div>

            {/* Slide count */}
            <div>
              <label className="block text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-1.5">
                Slide count — {slideCount}
              </label>
              <input
                type="range"
                min={4}
                max={30}
                value={slideCount}
                onChange={(e) => setSlideCount(Number(e.target.value))}
                className="w-full accent-[#5EFCAB]"
              />
              <div className="flex justify-between text-[10px] font-mono text-muted-foreground mt-0.5">
                <span>4</span>
                <span>30</span>
              </div>
            </div>

            {/* Style + Tone row */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-1.5">
                  Style
                </label>
                <select
                  value={style}
                  onChange={(e) => setStyle(e.target.value)}
                  className="w-full px-3 py-2 bg-depth-0 border border-border rounded-lg text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-[#5EFCAB]/30"
                >
                  {STYLES.map((s) => (
                    <option key={s} value={s}>
                      {s.charAt(0).toUpperCase() + s.slice(1)}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-1.5">
                  Tone
                </label>
                <select
                  value={tone}
                  onChange={(e) => setTone(e.target.value)}
                  className="w-full px-3 py-2 bg-depth-0 border border-border rounded-lg text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-[#5EFCAB]/30"
                >
                  {TONES.map((t) => (
                    <option key={t} value={t}>
                      {t.charAt(0).toUpperCase() + t.slice(1)}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Audience */}
            <div>
              <label className="block text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-1.5">
                Audience (optional)
              </label>
              <input
                type="text"
                value={audience}
                onChange={(e) => setAudience(e.target.value)}
                placeholder="e.g. clinical nurses, hospital administrators"
                className="w-full px-3 py-2 bg-depth-0 border border-border rounded-lg text-sm text-foreground placeholder-muted-foreground focus:outline-none focus:ring-1 focus:ring-[#5EFCAB]/30"
              />
            </div>
          </div>

          <DialogFooter>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setOpen(false)}
              disabled={busy}
            >
              Cancel
            </Button>
            <Button
              size="sm"
              onClick={() => void handleGenerate()}
              disabled={busy || !brief.trim()}
              className="bg-[#5EFCAB]/15 border border-[#5EFCAB]/30 text-[#5EFCAB] hover:bg-[#5EFCAB]/25"
            >
              {busy ? (
                <>
                  <Loader2 className="w-3 h-3 animate-spin mr-1" />
                  Generating...
                </>
              ) : (
                <>
                  <Presentation className="w-3 h-3 mr-1" />
                  Generate deck
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
