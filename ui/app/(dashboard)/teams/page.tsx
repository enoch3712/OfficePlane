'use client'

import { useState, useRef, useCallback } from 'react'
import { useSSE, type SSEEvent } from '@/hooks/useSSE'
import {
  Play,
  Square,
  Plus,
  Trash2,
  CheckCircle2,
  XCircle,
  Loader2,
  Terminal,
  UserCircle2,
} from 'lucide-react'
import { PageHeader } from '@/components/ui/page-header'
import { Badge } from '@/components/ui/badge'
import { StatusIndicator } from '@/components/ui/status-indicator'
import { cn } from '@/lib/cn'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001'

interface TeammateInput {
  role: string
  prompt: string
}

interface TeamJob {
  teamId: string
  streamUrl: string
  status: 'running' | 'completed' | 'failed' | 'cancelled'
  teammates: string[]
  result?: Record<string, unknown>
  error?: string
  durationMs?: number
}

const PRESETS = [
  {
    label: 'Pitch Deck Team',
    teammates: [
      { role: 'researcher', prompt: 'Research the topic thoroughly with data and statistics' },
      { role: 'designer', prompt: 'Design the slide structure, layout, and visual hierarchy' },
      { role: 'writer', prompt: 'Write compelling, concise slide content' },
    ],
  },
  {
    label: 'Code Review Team',
    teammates: [
      { role: 'security', prompt: 'Review for security vulnerabilities and best practices' },
      { role: 'performance', prompt: 'Analyze performance implications and bottlenecks' },
      { role: 'testing', prompt: 'Evaluate test coverage and suggest missing tests' },
    ],
  },
  {
    label: 'Debug Team',
    teammates: [
      { role: 'hypothesis_a', prompt: 'Investigate if this is a data/state issue' },
      { role: 'hypothesis_b', prompt: 'Investigate if this is a timing/race condition' },
      { role: 'hypothesis_c', prompt: 'Investigate if this is a configuration/environment issue' },
    ],
  },
]

export default function TeamsPage() {
  const [prompt, setPrompt] = useState('')
  const [model, setModel] = useState('')
  const [teammates, setTeammates] = useState<TeammateInput[]>([
    { role: 'researcher', prompt: '' },
    { role: 'writer', prompt: '' },
  ])
  const [team, setTeam] = useState<TeamJob | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const streamRef = useRef<HTMLDivElement>(null)

  const handleEvent = useCallback((event: SSEEvent) => {
    if (event.event === 'team_completed' || event.event === 'team_failed') {
      const data = event.data
      setTeam((prev) =>
        prev
          ? {
              ...prev,
              status: event.event === 'team_failed' ? 'failed' : 'completed',
              durationMs: data.duration_ms as number | undefined,
              error: data.error as string | undefined,
            }
          : prev,
      )
    } else if (event.event === 'team_started') {
      setTeam((prev) => (prev ? { ...prev, status: 'running' } : prev))
    }

    requestAnimationFrame(() => {
      if (streamRef.current) {
        streamRef.current.scrollTop = streamRef.current.scrollHeight
      }
    })
  }, [])

  const streamUrl = team?.streamUrl ?? null
  const { events, reset: resetSSE } = useSSE(streamUrl, {
    onEvent: handleEvent,
    autoConnect: true,
  })

  const addTeammate = () => {
    setTeammates((prev) => [...prev, { role: '', prompt: '' }])
  }

  const removeTeammate = (idx: number) => {
    setTeammates((prev) => prev.filter((_, i) => i !== idx))
  }

  const updateTeammate = (idx: number, field: 'role' | 'prompt', value: string) => {
    setTeammates((prev) => prev.map((t, i) => (i === idx ? { ...t, [field]: value } : t)))
  }

  const applyPreset = (preset: (typeof PRESETS)[number]) => {
    setTeammates(preset.teammates.map((t) => ({ ...t })))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!prompt.trim() || isSubmitting) return

    const validTeammates = teammates.filter((t) => t.role.trim())
    if (validTeammates.length < 1) return

    resetSSE()
    setTeam(null)
    setIsSubmitting(true)

    try {
      const body: Record<string, unknown> = {
        prompt: prompt.trim(),
        teammates: validTeammates.map((t) => ({
          role: t.role.trim(),
          prompt: t.prompt.trim() || undefined,
        })),
      }
      if (model.trim()) body.model = model.trim()

      const res = await fetch(`${API_URL}/api/teams`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })

      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Failed to start team')
      }

      const data = await res.json()
      setTeam({
        teamId: data.team_id,
        streamUrl: data.stream_url,
        status: 'running',
        teammates: data.teammates,
      })
    } catch (err) {
      setTeam({
        teamId: '',
        streamUrl: '',
        status: 'failed',
        teammates: [],
        error: err instanceof Error ? err.message : 'Unknown error',
      })
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleCancel = async () => {
    if (!team?.teamId) return
    try {
      await fetch(`${API_URL}/api/teams/${team.teamId}`, { method: 'DELETE' })
      setTeam((prev) => (prev ? { ...prev, status: 'cancelled' } : prev))
    } catch (err) {
      console.error('Failed to cancel:', err)
    }
  }

  const isRunning = team?.status === 'running'

  return (
    <div className="max-w-7xl mx-auto">
      <PageHeader
        title="Agent Teams"
        subtitle="Coordinate multiple AI agents working in parallel"
        breadcrumbs={[{ label: 'Dashboard' }, { label: 'Teams' }]}
      />

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* Left: Config (2 cols) */}
        <div className="lg:col-span-2 space-y-4">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-2">
                Task
              </label>
              <textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder="Create a pitch deck about AI in healthcare..."
                className="w-full h-28 px-4 py-3 bg-depth-1 border border-border rounded-lg text-foreground placeholder-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary/30 focus:border-primary/50 resize-none"
                disabled={isRunning}
              />
            </div>

            {/* Presets */}
            <div>
              <label className="block text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-2">
                Presets
              </label>
              <div className="flex flex-wrap gap-2">
                {PRESETS.map((p) => (
                  <button
                    key={p.label}
                    type="button"
                    onClick={() => applyPreset(p)}
                    disabled={isRunning}
                    className="px-3 py-1.5 text-xs bg-depth-1 border border-border rounded-lg text-muted-foreground hover:bg-depth-2 hover:text-foreground disabled:opacity-40 transition-colors"
                  >
                    {p.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Teammates */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
                  Teammates
                </label>
                <button
                  type="button"
                  onClick={addTeammate}
                  disabled={isRunning || teammates.length >= 10}
                  className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground disabled:opacity-40"
                >
                  <Plus className="w-3.5 h-3.5" /> Add
                </button>
              </div>
              <div className="space-y-2">
                {teammates.map((t, i) => (
                  <div key={i} className="flex gap-2">
                    <input
                      type="text"
                      value={t.role}
                      onChange={(e) => updateTeammate(i, 'role', e.target.value)}
                      placeholder="Role"
                      className="w-28 px-3 py-2 bg-depth-1 border border-border rounded-lg text-foreground text-sm placeholder-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary/30"
                      disabled={isRunning}
                    />
                    <input
                      type="text"
                      value={t.prompt}
                      onChange={(e) => updateTeammate(i, 'prompt', e.target.value)}
                      placeholder="Instructions (optional)"
                      className="flex-1 px-3 py-2 bg-depth-1 border border-border rounded-lg text-foreground text-sm placeholder-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary/30"
                      disabled={isRunning}
                    />
                    {teammates.length > 1 && (
                      <button
                        type="button"
                        onClick={() => removeTeammate(i)}
                        disabled={isRunning}
                        className="p-2 text-muted-foreground hover:text-red-400 disabled:opacity-40"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* Model */}
            <div>
              <label className="block text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-1.5">
                Model
              </label>
              <input
                type="text"
                value={model}
                onChange={(e) => setModel(e.target.value)}
                placeholder="gpt-4o (default)"
                className="w-full px-3 py-2 bg-depth-1 border border-border rounded-lg text-foreground text-sm placeholder-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary/30"
                disabled={isRunning}
              />
            </div>

            {/* Actions */}
            <div className="flex gap-3">
              {!isRunning ? (
                <button
                  type="submit"
                  disabled={!prompt.trim() || teammates.filter((t) => t.role.trim()).length < 1 || isSubmitting}
                  className="flex items-center gap-2 px-5 py-2.5 bg-primary/15 border border-primary/30 text-primary rounded-lg font-medium text-sm hover:bg-primary/25 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                >
                  {isSubmitting ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Play className="w-4 h-4" />
                  )}
                  Start Team
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

          {/* Result */}
          {team && !isRunning && (
            <div
              className={cn(
                'p-4 rounded-lg border border-l-[3px]',
                team.status === 'completed'
                  ? 'border-l-primary bg-depth-1'
                  : team.status === 'failed'
                    ? 'border-l-red-400 bg-depth-1'
                    : 'border-l-border bg-depth-1'
              )}
            >
              <div className="flex items-center gap-2 mb-2">
                <StatusIndicator status={team.status === 'completed' ? 'completed' : 'error'} />
                <span className="text-sm font-medium text-foreground capitalize">{team.status}</span>
                {team.durationMs && (
                  <span className="text-xs font-mono text-muted-foreground ml-auto">
                    {(team.durationMs / 1000).toFixed(1)}s
                  </span>
                )}
              </div>
              {team.error && <p className="text-sm text-red-400">{team.error}</p>}
            </div>
          )}
        </div>

        {/* Right: Stream Output (3 cols) */}
        <div className="lg:col-span-3 bg-depth-1 border border-border rounded-lg overflow-hidden flex flex-col h-[700px]">
          <div className="flex items-center gap-2 px-4 py-3 border-b border-border">
            <Terminal className="w-4 h-4 text-muted-foreground" />
            <span className="text-sm font-medium text-foreground">Team Activity</span>
            {isRunning && (
              <span className="flex items-center gap-1.5 ml-auto">
                <StatusIndicator status="active" />
                <span className="text-[10px] font-mono text-muted-foreground">Running</span>
              </span>
            )}
          </div>
          <div ref={streamRef} className="flex-1 overflow-y-auto p-4 font-mono text-sm space-y-1.5 scrollbar-thin">
            {events.length === 0 && !isRunning && (
              <p className="text-muted-foreground/50 italic">Team activity will appear here...</p>
            )}
            {events.map((evt, i) => (
              <TeamEventLine key={i} event={evt} />
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

function TeamEventLine({ event }: { event: SSEEvent }) {
  const data = event.data
  const agent = data.agent_id as string | undefined

  const agentBadge = agent ? (
    <Badge variant={agent === 'lead' ? 'accent' : 'info'}>
      <UserCircle2 className="w-3 h-3 mr-1" />
      {agent}
    </Badge>
  ) : null

  switch (event.event) {
    case 'team_started':
      return (
        <div className="text-primary flex items-center gap-2">
          {agentBadge}
          Team started with {data.teammates as number} teammates
        </div>
      )
    case 'decomposing':
      return (
        <div className="text-muted-foreground flex items-center gap-2">
          {agentBadge}
          Decomposing work into tasks...
        </div>
      )
    case 'tasks_created': {
      const tasks = data.tasks as Array<{ id: string; title: string }> | undefined
      return (
        <div className="space-y-1">
          <div className="text-foreground/80 flex items-center gap-2">
            {agentBadge}
            Created {data.count as number} tasks:
          </div>
          {tasks?.map((t) => (
            <div key={t.id} className="pl-6 text-muted-foreground">
              {t.id}: {t.title}
            </div>
          ))}
        </div>
      )
    }
    case 'teammates_started': {
      const tms = data.teammates as Array<{ id: string; role: string }> | undefined
      return (
        <div className="text-primary/80 flex items-center gap-2">
          {agentBadge}
          Teammates active: {tms?.map((t) => t.role).join(', ')}
        </div>
      )
    }
    case 'task_claimed':
      return (
        <div className="text-foreground/70 flex items-center gap-2">
          {agentBadge}
          Claimed: {data.title as string}
        </div>
      )
    case 'task_completed':
      return (
        <div className="space-y-1">
          <div className="text-primary flex items-center gap-2">
            {agentBadge}
            <CheckCircle2 className="w-3.5 h-3.5" />
            Completed: {data.task_id as string}
          </div>
          {data.result ? (
            <div className="pl-6 text-muted-foreground whitespace-pre-wrap">
              {String(data.result).slice(0, 300)}
              {String(data.result).length > 300 ? '...' : ''}
            </div>
          ) : null}
        </div>
      )
    case 'task_failed':
      return (
        <div className="text-red-400 flex items-center gap-2">
          {agentBadge}
          <XCircle className="w-3.5 h-3.5" />
          Failed: {data.error as string}
        </div>
      )
    case 'synthesizing':
      return (
        <div className="text-primary flex items-center gap-2 mt-2">
          {agentBadge}
          Synthesizing results...
        </div>
      )
    case 'team_completed': {
      const summary = data.summary as Record<string, number> | undefined
      return (
        <div className="text-primary mt-2 border-t border-border pt-2">
          Team completed
          {summary &&
            ` — ${summary.completed || 0} done, ${summary.failed || 0} failed`}
          {data.duration_ms ? ` (${((data.duration_ms as number) / 1000).toFixed(1)}s)` : null}
        </div>
      )
    }
    case 'team_failed':
      return (
        <div className="text-red-400 mt-2 border-t border-border pt-2">
          Team failed: {data.error as string}
        </div>
      )
    default:
      return (
        <div className="text-muted-foreground/50">
          [{event.event}] {JSON.stringify(data)}
        </div>
      )
  }
}
