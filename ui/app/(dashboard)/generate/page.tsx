'use client'

import { useState, useRef, useCallback, useEffect } from 'react'
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
  FolderOpen,
  Download,
  Link2,
  Radio,
} from 'lucide-react'
import { PageHeader } from '@/components/ui/page-header'
import { Badge } from '@/components/ui/badge'
import { StatusIndicator } from '@/components/ui/status-indicator'
import { cn } from '@/lib/cn'
import { streamSkill, type ProgressEvent } from '@/lib/api/streaming'
import { StreamingProgress } from '@/components/generate/StreamingProgress'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001'

type OutputFormat = 'pptx' | 'html' | 'both'
type CollectionFormat = 'docx' | 'pptx'

interface Collection {
  collection_id: string
  name: string
  description: string | null
  document_count: number
}

interface CollectionResult {
  file_path: string
  file_url: string
  title: string
  model: string
  format: string
  source_document_count: number
  source_document_ids: string[]
  slide_count?: number
  node_count?: number
}

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

  // --- SSE streaming state ---
  const [streamBrief, setStreamBrief] = useState('')
  const [streamSourceIds, setStreamSourceIds] = useState('')
  const [streamEvents, setStreamEvents] = useState<ProgressEvent[]>([])
  const [streamStatus, setStreamStatus] = useState<'idle' | 'running' | 'done' | 'error'>('idle')
  const [streamResult, setStreamResult] = useState<Record<string, unknown> | null>(null)
  const [streamError, setStreamError] = useState<string | null>(null)
  const streamAbortRef = useRef<AbortController | null>(null)

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

  const handleStreamGenerate = async () => {
    if (!streamBrief.trim() || !streamSourceIds.trim() || streamStatus === 'running') return
    const ids = streamSourceIds.split(',').map((s) => s.trim()).filter(Boolean)
    if (!ids.length) return

    if (streamAbortRef.current) streamAbortRef.current.abort()
    const ctrl = new AbortController()
    streamAbortRef.current = ctrl

    setStreamEvents([])
    setStreamResult(null)
    setStreamError(null)
    setStreamStatus('running')

    try {
      await streamSkill(
        'generate-docx',
        { source_document_ids: ids, brief: streamBrief.trim() },
        ({ name, data }) => {
          if (name === 'progress') {
            setStreamEvents((prev) => [...prev, data as unknown as ProgressEvent])
          } else if (name === 'result') {
            setStreamResult(data)
          }
        },
        ctrl.signal,
      )
      setStreamStatus('done')
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        setStreamError(err instanceof Error ? err.message : 'Stream failed')
        setStreamStatus('error')
      }
    }
  }

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

      {/* SSE Streaming Generate (docx) */}
      <div className="mt-10 pt-8 border-t border-border">
        <div className="flex items-center gap-2 mb-5">
          <Radio className="w-4 h-4 text-primary" />
          <h2 className="text-base font-semibold text-foreground">Generate DOCX (stream)</h2>
          <Badge variant="neutral" className="text-[10px] font-mono ml-1">phase 24</Badge>
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="space-y-4">
            <div>
              <label className="block text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-1.5">
                Source Document IDs (comma-separated)
              </label>
              <input
                type="text"
                value={streamSourceIds}
                onChange={(e) => setStreamSourceIds(e.target.value)}
                placeholder="uuid1, uuid2, …"
                className="w-full px-3 py-2 bg-depth-1 border border-border rounded-lg text-foreground text-sm placeholder-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary/30"
                disabled={streamStatus === 'running'}
              />
            </div>
            <div>
              <label className="block text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-1.5">
                Brief
              </label>
              <textarea
                value={streamBrief}
                onChange={(e) => setStreamBrief(e.target.value)}
                placeholder="Describe the document you want to produce…"
                className="w-full h-28 px-4 py-3 bg-depth-1 border border-border rounded-lg text-foreground placeholder-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary/30 resize-none text-sm"
                disabled={streamStatus === 'running'}
              />
            </div>
            <button
              type="button"
              onClick={handleStreamGenerate}
              disabled={!streamBrief.trim() || !streamSourceIds.trim() || streamStatus === 'running'}
              className="flex items-center gap-2 px-5 py-2.5 bg-primary/15 border border-primary/30 text-primary rounded-lg font-medium text-sm hover:bg-primary/25 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              {streamStatus === 'running' ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Radio className="w-4 h-4" />
              )}
              Generate (stream)
            </button>
          </div>
          <div className="space-y-3">
            <StreamingProgress events={streamEvents} status={streamStatus} />
            {streamError && (
              <div className="p-3 rounded-lg border border-l-[3px] border-l-red-400 bg-depth-1 text-sm text-red-400">
                {streamError}
              </div>
            )}
            {streamResult && (
              <div className="p-4 rounded-lg border border-l-[3px] border-l-primary bg-depth-1 space-y-2">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-primary" />
                  <span className="text-sm font-medium text-foreground">
                    {(streamResult.title as string) ?? 'Done'}
                  </span>
                </div>
                <div className="text-xs text-muted-foreground font-mono space-y-0.5">
                  {streamResult.node_count !== undefined && <div>Nodes: {streamResult.node_count as number}</div>}
                  {!!streamResult.model && <div>Model: {streamResult.model as string}</div>}
                </div>
                {!!streamResult.file_url && (
                  <a
                    href={`${API_URL}${streamResult.file_url as string}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 text-sm text-primary hover:underline"
                  >
                    <Download className="w-3.5 h-3.5" />
                    Download DOCX
                  </a>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      <GenerateFromCollection />
    </div>
  )
}

function GenerateFromCollection() {
  const [collections, setCollections] = useState<Collection[]>([])
  const [loadingCollections, setLoadingCollections] = useState(false)
  const [collectionId, setCollectionId] = useState('')
  const [brief, setBrief] = useState('')
  const [format, setFormat] = useState<CollectionFormat>('docx')
  const [audience, setAudience] = useState('')
  const [tone, setTone] = useState('')
  const [slideCount, setSlideCount] = useState('10')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [result, setResult] = useState<CollectionResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setLoadingCollections(true)
    fetch(`${API_URL}/api/ecm/collections`)
      .then((r) => r.json())
      .then((data) => {
        setCollections(data.collections ?? [])
      })
      .catch(() => setCollections([]))
      .finally(() => setLoadingCollections(false))
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!collectionId || !brief.trim() || isSubmitting) return
    setIsSubmitting(true)
    setResult(null)
    setError(null)

    try {
      const inputs: Record<string, unknown> = {
        collection_id: collectionId,
        brief: brief.trim(),
        format,
      }
      if (audience.trim()) inputs.audience = audience.trim()
      if (tone.trim()) inputs.tone = tone.trim()
      if (format === 'pptx' && slideCount) inputs.slide_count = parseInt(slideCount, 10)

      const res = await fetch(`${API_URL}/api/jobs/invoke/generate-from-collection`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ inputs }),
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Generation failed')
      }
      const data = await res.json()
      setResult(data.output as CollectionResult)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setIsSubmitting(false)
    }
  }

  const jobId = result?.file_url?.split('/')[3]

  return (
    <div className="mt-10 pt-8 border-t border-border">
      <div className="flex items-center gap-2 mb-5">
        <FolderOpen className="w-4 h-4 text-primary" />
        <h2 className="text-base font-semibold text-foreground">Generate from Collection</h2>
        <Badge variant="neutral" className="text-[10px] font-mono ml-1">new</Badge>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-1.5">
              Collection
            </label>
            {loadingCollections ? (
              <div className="flex items-center gap-2 px-3 py-2 text-sm text-muted-foreground">
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                Loading collections...
              </div>
            ) : (
              <select
                value={collectionId}
                onChange={(e) => setCollectionId(e.target.value)}
                className="w-full px-3 py-2 bg-depth-1 border border-border rounded-lg text-foreground text-sm focus:outline-none focus:ring-1 focus:ring-primary/30"
                disabled={isSubmitting}
              >
                <option value="">Select a collection…</option>
                {collections.map((c) => (
                  <option key={c.collection_id} value={c.collection_id}>
                    {c.name} ({c.document_count} doc{c.document_count !== 1 ? 's' : ''})
                  </option>
                ))}
              </select>
            )}
          </div>

          <div>
            <label className="block text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-1.5">
              Brief
            </label>
            <textarea
              value={brief}
              onChange={(e) => setBrief(e.target.value)}
              placeholder="Describe the combined document you want to produce…"
              className="w-full h-28 px-4 py-3 bg-depth-1 border border-border rounded-lg text-foreground placeholder-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary/30 resize-none text-sm"
              disabled={isSubmitting}
            />
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div>
              <label className="block text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-1.5">
                Format
              </label>
              <select
                value={format}
                onChange={(e) => setFormat(e.target.value as CollectionFormat)}
                className="w-full px-3 py-2 bg-depth-1 border border-border rounded-lg text-foreground text-sm focus:outline-none focus:ring-1 focus:ring-primary/30"
                disabled={isSubmitting}
              >
                <option value="docx">DOCX</option>
                <option value="pptx">PPTX</option>
              </select>
            </div>
            {format === 'pptx' && (
              <div>
                <label className="block text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-1.5">
                  Slides
                </label>
                <input
                  type="number"
                  value={slideCount}
                  onChange={(e) => setSlideCount(e.target.value)}
                  min={1}
                  max={50}
                  className="w-full px-3 py-2 bg-depth-1 border border-border rounded-lg text-foreground text-sm focus:outline-none focus:ring-1 focus:ring-primary/30"
                  disabled={isSubmitting}
                />
              </div>
            )}
            <div>
              <label className="block text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-1.5">
                Audience
              </label>
              <input
                type="text"
                value={audience}
                onChange={(e) => setAudience(e.target.value)}
                placeholder="general"
                className="w-full px-3 py-2 bg-depth-1 border border-border rounded-lg text-foreground text-sm placeholder-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary/30"
                disabled={isSubmitting}
              />
            </div>
            <div>
              <label className="block text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-1.5">
                Tone
              </label>
              <input
                type="text"
                value={tone}
                onChange={(e) => setTone(e.target.value)}
                placeholder="neutral"
                className="w-full px-3 py-2 bg-depth-1 border border-border rounded-lg text-foreground text-sm placeholder-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary/30"
                disabled={isSubmitting}
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={!collectionId || !brief.trim() || isSubmitting}
            className="flex items-center gap-2 px-5 py-2.5 bg-primary/15 border border-primary/30 text-primary rounded-lg font-medium text-sm hover:bg-primary/25 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            {isSubmitting ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Play className="w-4 h-4" />
            )}
            Generate
          </button>
        </form>

        {/* Result panel */}
        <div className="space-y-3">
          {error && (
            <div className="p-4 rounded-lg border border-l-[3px] border-l-red-400 bg-depth-1">
              <div className="flex items-center gap-2 mb-1">
                <XCircle className="w-4 h-4 text-red-400" />
                <span className="text-sm font-medium text-red-400">Error</span>
              </div>
              <p className="text-sm text-red-400/80">{error}</p>
            </div>
          )}
          {result && (
            <div className="p-4 rounded-lg border border-l-[3px] border-l-primary bg-depth-1 space-y-3">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-primary" />
                <span className="text-sm font-medium text-foreground">{result.title}</span>
                <span className="ml-auto text-[10px] font-mono text-muted-foreground uppercase">
                  {result.format}
                </span>
              </div>
              <div className="text-xs text-muted-foreground font-mono space-y-0.5">
                <div>Sources: {result.source_document_count}</div>
                {result.slide_count !== undefined && <div>Slides: {result.slide_count}</div>}
                {result.node_count !== undefined && <div>Nodes: {result.node_count}</div>}
                <div className="text-[10px] opacity-60">Model: {result.model}</div>
              </div>
              <div className="flex items-center gap-3 flex-wrap">
                <a
                  href={`${API_URL}${result.file_url}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 text-sm text-primary hover:underline"
                >
                  <Download className="w-3.5 h-3.5" />
                  Download {result.format.toUpperCase()}
                </a>
                {jobId && (
                  <a
                    href={`/lineage?workspace=${jobId}`}
                    className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
                  >
                    <Link2 className="w-3.5 h-3.5" />
                    View source trail
                    <ExternalLink className="w-3 h-3" />
                  </a>
                )}
              </div>
            </div>
          )}
          {!result && !error && !isSubmitting && (
            <div className="p-4 rounded-lg border border-dashed border-border bg-depth-1/50 text-center">
              <FolderOpen className="w-8 h-8 text-muted-foreground/30 mx-auto mb-2" />
              <p className="text-sm text-muted-foreground/60">
                Select a collection and write a brief to combine all its documents into one file.
              </p>
            </div>
          )}
          {isSubmitting && (
            <div className="p-4 rounded-lg border border-border bg-depth-1 flex items-center gap-3">
              <Loader2 className="w-5 h-5 animate-spin text-primary" />
              <span className="text-sm text-muted-foreground">Generating combined document…</span>
            </div>
          )}
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
