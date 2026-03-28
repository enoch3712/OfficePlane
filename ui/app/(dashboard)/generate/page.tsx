'use client'

import { useState, useRef, useCallback } from 'react'
import { useSSE, type SSEEvent } from '@/hooks/useSSE'
import {
  Play,
  Square,
  FileText,
  Code,
  Terminal,
  CheckCircle2,
  XCircle,
  Loader2,
  ExternalLink,
} from 'lucide-react'
import { PageHeader } from '@/components/ui/page-header'
import { Badge } from '@/components/ui/badge'
import { StatusIndicator } from '@/components/ui/status-indicator'
import { cn } from '@/lib/cn'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001'

type OutputFormat = 'pptx' | 'html' | 'both'

interface GenerateJob {
  jobId: string
  streamUrl: string
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled'
  documentId?: string
  error?: string
  durationMs?: number
}

export default function GeneratePage() {
  const [prompt, setPrompt] = useState('')
  const [outputFormat, setOutputFormat] = useState<OutputFormat>('pptx')
  const [model, setModel] = useState('')
  const [slideCount, setSlideCount] = useState('')
  const [job, setJob] = useState<GenerateJob | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const streamOutputRef = useRef<HTMLDivElement>(null)

  const handleEvent = useCallback((event: SSEEvent) => {
    if (event.event === 'start') {
      setJob((prev) => prev ? { ...prev, status: 'running' } : prev)
    } else if (event.event === 'stop') {
      const data = event.data as Record<string, unknown>
      setJob((prev) =>
        prev
          ? {
              ...prev,
              status: data.status === 'failed' ? 'failed' : 'completed',
              documentId: data.document_id as string | undefined,
              error: data.error as string | undefined,
              durationMs: data.duration_ms as number | undefined,
            }
          : prev,
      )
    }

    requestAnimationFrame(() => {
      if (streamOutputRef.current) {
        streamOutputRef.current.scrollTop = streamOutputRef.current.scrollHeight
      }
    })
  }, [])

  const streamUrl = job?.streamUrl ?? null
  const { events, reset: resetSSE } = useSSE(streamUrl, {
    onEvent: handleEvent,
    autoConnect: true,
  })

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!prompt.trim() || isSubmitting) return

    resetSSE()
    setJob(null)
    setIsSubmitting(true)

    try {
      const body: Record<string, unknown> = {
        prompt: prompt.trim(),
        output_format: outputFormat,
        options: {},
      }
      if (model.trim()) body.model = model.trim()
      if (slideCount) body.options = { slide_count_hint: parseInt(slideCount, 10) }

      const res = await fetch(`${API_URL}/api/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })

      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Failed to start generation')
      }

      const data = await res.json()
      setJob({
        jobId: data.job_id,
        streamUrl: data.stream_url,
        status: 'queued',
      })
    } catch (err) {
      setJob({
        jobId: '',
        streamUrl: '',
        status: 'failed',
        error: err instanceof Error ? err.message : 'Unknown error',
      })
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleCancel = async () => {
    if (!job?.jobId) return
    try {
      await fetch(`${API_URL}/api/generate/${job.jobId}`, { method: 'DELETE' })
      setJob((prev) => (prev ? { ...prev, status: 'cancelled' } : prev))
    } catch (err) {
      console.error('Failed to cancel:', err)
    }
  }

  const isRunning = job?.status === 'queued' || job?.status === 'running'

  return (
    <div className="max-w-6xl mx-auto">
      <PageHeader
        title="Generate"
        subtitle="Create presentations and documents with AI agents"
        breadcrumbs={[{ label: 'Dashboard' }, { label: 'Generate' }]}
      />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left: Input Form */}
        <div className="space-y-4">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-2">
                Prompt
              </label>
              <textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder="Create a 10-slide pitch deck about AI in healthcare..."
                className="w-full h-40 px-4 py-3 bg-depth-1 border border-border rounded-lg text-foreground placeholder-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary/30 focus:border-primary/50 resize-none"
                disabled={isRunning}
              />
            </div>

            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="block text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-1.5">
                  Format
                </label>
                <select
                  value={outputFormat}
                  onChange={(e) => setOutputFormat(e.target.value as OutputFormat)}
                  className="w-full px-3 py-2 bg-depth-1 border border-border rounded-lg text-foreground text-sm focus:outline-none focus:ring-1 focus:ring-primary/30"
                  disabled={isRunning}
                >
                  <option value="pptx">PPTX</option>
                  <option value="html">HTML</option>
                  <option value="both">Both</option>
                </select>
              </div>
              <div>
                <label className="block text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-1.5">
                  Model
                </label>
                <input
                  type="text"
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  placeholder="gpt-4o"
                  className="w-full px-3 py-2 bg-depth-1 border border-border rounded-lg text-foreground text-sm placeholder-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary/30"
                  disabled={isRunning}
                />
              </div>
              <div>
                <label className="block text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-1.5">
                  Slides
                </label>
                <input
                  type="number"
                  value={slideCount}
                  onChange={(e) => setSlideCount(e.target.value)}
                  placeholder="Auto"
                  min={1}
                  max={50}
                  className="w-full px-3 py-2 bg-depth-1 border border-border rounded-lg text-foreground text-sm placeholder-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary/30"
                  disabled={isRunning}
                />
              </div>
            </div>

            <div className="flex gap-3">
              {!isRunning ? (
                <button
                  type="submit"
                  disabled={!prompt.trim() || isSubmitting}
                  className="flex items-center gap-2 px-5 py-2.5 bg-primary/15 border border-primary/30 text-primary rounded-lg font-medium text-sm hover:bg-primary/25 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                >
                  {isSubmitting ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Play className="w-4 h-4" />
                  )}
                  Generate
                </button>
              ) : (
                <button
                  type="button"
                  onClick={handleCancel}
                  className="flex items-center gap-2 px-5 py-2.5 bg-red-500/15 border border-red-500/30 text-red-400 rounded-lg font-medium text-sm hover:bg-red-500/25 transition-colors"
                >
                  <Square className="w-4 h-4" />
                  Cancel
                </button>
              )}
            </div>
          </form>

          {/* Job Result */}
          {job && !isRunning && (
            <div
              className={cn(
                'p-4 rounded-lg border border-l-[3px]',
                job.status === 'completed'
                  ? 'border-l-primary bg-depth-1'
                  : job.status === 'failed'
                    ? 'border-l-red-400 bg-depth-1'
                    : 'border-l-border bg-depth-1'
              )}
            >
              <div className="flex items-center gap-2 mb-2">
                <StatusIndicator status={job.status === 'completed' ? 'completed' : 'error'} />
                <span className="text-sm font-medium text-foreground capitalize">{job.status}</span>
                {job.durationMs && (
                  <span className="text-xs font-mono text-muted-foreground ml-auto">
                    {(job.durationMs / 1000).toFixed(1)}s
                  </span>
                )}
              </div>
              {job.error && <p className="text-sm text-red-400">{job.error}</p>}
              {job.documentId && (
                <a
                  href={`/documents?id=${job.documentId}`}
                  className="inline-flex items-center gap-1.5 text-sm text-primary hover:underline mt-1"
                >
                  <FileText className="w-4 h-4" />
                  View Document
                  <ExternalLink className="w-3 h-3" />
                </a>
              )}
            </div>
          )}
        </div>

        {/* Right: Stream Output */}
        <div className="bg-depth-1 border border-border rounded-lg overflow-hidden flex flex-col h-[600px]">
          <div className="flex items-center gap-2 px-4 py-3 border-b border-border">
            <Terminal className="w-4 h-4 text-muted-foreground" />
            <span className="text-sm font-medium text-foreground">Agent Output</span>
            {isRunning && (
              <span className="flex items-center gap-1.5 ml-auto">
                <StatusIndicator status="active" />
                <span className="text-[10px] font-mono text-muted-foreground">Streaming</span>
              </span>
            )}
          </div>
          <div
            ref={streamOutputRef}
            className="flex-1 overflow-y-auto p-4 font-mono text-sm space-y-1 scrollbar-thin"
          >
            {events.length === 0 && !isRunning && (
              <p className="text-muted-foreground/50 italic">Output will appear here when generation starts...</p>
            )}
            {events.map((evt, i) => (
              <EventLine key={i} event={evt} />
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

function EventLine({ event }: { event: SSEEvent }) {
  const data = event.data

  switch (event.event) {
    case 'start':
      return <div className="text-muted-foreground">--- Generation started ---</div>
    case 'delta':
      return <div className="text-foreground/80">{data.text as string}</div>
    case 'tool_call': {
      const args = data.arguments as Record<string, unknown> | undefined
      return (
        <div className="flex items-start gap-2 text-primary/80">
          <Code className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
          <span>
            {data.name as string}
            {args?.command ? `: ${args.command as string}` : ''}
          </span>
        </div>
      )
    }
    case 'tool_result': {
      const isError = data.is_error as boolean
      return (
        <div className={cn('pl-5', isError ? 'text-red-400' : 'text-muted-foreground')}>
          {(data.result as string)?.slice(0, 500)}
        </div>
      )
    }
    case 'stop': {
      const failed = data.status === 'failed'
      return (
        <div className={cn('mt-2', failed ? 'text-red-400' : 'text-primary')}>
          --- {failed ? 'Failed' : 'Completed'} ({((data.duration_ms as number) / 1000).toFixed(1)}s) ---
        </div>
      )
    }
    case 'error':
      return <div className="text-red-400">{data.message as string}</div>
    default:
      return <div className="text-muted-foreground/50">[{event.event}] {JSON.stringify(data)}</div>
  }
}
