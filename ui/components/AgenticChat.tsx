'use client'

import { useEffect, useMemo, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type {
  OrchestrationSummary,
  PlanActionNode,
  PlanResponse,
  VerificationResult,
} from '@/lib/types'
import {
  Bot,
  CheckCircle,
  CheckCircle2,
  Download,
  FileText,
  Loader2,
  Play,
  RefreshCw,
  Send,
  ShieldCheck,
  Sparkles,
  User,
  Workflow,
  XCircle,
} from 'lucide-react'

type ChatAction = 'planning'

interface AgenticChatProps {
  selectedDocumentId?: string
}

type ChatMessage = {
  id: string
  role: 'user' | 'assistant' | 'error' | 'execution' | 'verification'
  content: string
  actionLabel?: string
  plan?: PlanResponse
  executionResult?: {
    success: boolean
    completed: number
    failed: number
    total: number
  }
  verificationResult?: VerificationResult
  originalRequest?: string
}

const ACTION_LABELS: Record<ChatAction, string> = {
  planning: 'Agentic Planning',
}

const formatActionLabel = (node: PlanActionNode) => {
  const title = node.inputs?.title ? `: ${node.inputs.title}` : ''
  return `${node.action}${title}`
}

const getStatusStyle = (status?: string) => {
  switch (status) {
    case 'completed':
      return 'bg-green-500/10 text-green-400 border-green-500/20'
    case 'failed':
      return 'bg-red-500/10 text-red-400 border-red-500/20'
    case 'running':
      return 'bg-blue-500/10 text-blue-400 border-blue-500/20'
    default:
      return 'bg-white/5 text-slate-400 border-white/10'
  }
}

const formatModeLabel = (value?: string | null) => {
  if (!value) return 'unknown'
  return value.replace(/_/g, ' ')
}

const formatSignalValue = (value: unknown) => {
  if (typeof value === 'number') {
    return value.toFixed(value <= 1 ? 2 : 0)
  }
  return String(value)
}

const renderOrchestration = (summary?: OrchestrationSummary) => {
  if (!summary) return null

  return (
    <div className="rounded-lg border border-indigo-200 bg-indigo-50 p-4">
      <div className="flex items-center gap-2 text-sm font-semibold text-indigo-900">
        <Workflow className="h-4 w-4" />
        {summary.strategy} · {formatModeLabel(summary.final_mode)}
      </div>

      <div className="mt-2 flex flex-wrap gap-2 text-xs text-indigo-800">
        <span className="rounded-full bg-white/80 px-2 py-1">
          initial: {formatModeLabel(summary.initial_mode)}
        </span>
        <span className="rounded-full bg-white/80 px-2 py-1">
          attempts: {summary.worker_attempts}
        </span>
        {summary.worker_confidence !== undefined && summary.worker_confidence !== null && (
          <span className="rounded-full bg-white/80 px-2 py-1">
            confidence: {summary.worker_confidence.toFixed(2)}
          </span>
        )}
        {summary.takeover_reason && (
          <span className="rounded-full bg-amber-100 px-2 py-1 text-amber-900">
            takeover: {summary.takeover_reason}
          </span>
        )}
      </div>

      {Object.keys(summary.signals).length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {Object.entries(summary.signals).map(([key, value]) => (
            <span
              key={key}
              className="rounded-full border border-indigo-200 bg-white px-2 py-1 text-xs text-indigo-700"
            >
              {key}: {formatSignalValue(value)}
            </span>
          ))}
        </div>
      )}

      {summary.transitions.length > 0 && (
        <div className="mt-3 space-y-2">
          {summary.transitions.map((transition, index) => (
            <div
              key={`${transition.state}-${index}`}
              className="rounded-md border border-indigo-100 bg-white px-3 py-2"
            >
              <div className="flex items-center justify-between gap-3 text-xs font-semibold uppercase tracking-wide text-indigo-700">
                <span>{transition.state}</span>
                <span>{transition.action}</span>
              </div>
              <div className="mt-1 text-sm text-indigo-900">{transition.reason}</div>
            </div>
          ))}
        </div>
      )}

      {summary.validation_issues.length > 0 && (
        <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
          {summary.validation_issues.join(' ')}
        </div>
      )}
    </div>
  )
}

const renderNode = (node: PlanActionNode, depth = 0) => {
  const inputEntries = Object.entries(node.inputs || {}).filter(
    ([key, value]) => key !== 'content' && key !== 'content_outline' && value !== undefined
  )

  const statusStyle = getStatusStyle(node.status)
  const isCompleted = node.status === 'completed'
  const isFailed = node.status === 'failed'

  return (
    <div key={node.id} className="space-y-2" style={{ marginLeft: depth * 12 }}>
      <div className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-sm ${
        isCompleted ? 'border-green-500/20 bg-green-500/10' :
        isFailed ? 'border-red-500/20 bg-red-500/10' :
        'border-white/10 bg-white/[0.02]'
      }`}>
        {isCompleted && <CheckCircle className="h-4 w-4 text-green-400 flex-shrink-0" />}
        {isFailed && <XCircle className="h-4 w-4 text-red-400 flex-shrink-0" />}
        <span className={`font-medium ${isCompleted ? 'text-green-400' : isFailed ? 'text-red-400' : 'text-white'}`}>
          {formatActionLabel(node)}
        </span>
        {node.status && (
          <span className={`ml-auto rounded-full px-2 py-0.5 text-xs border ${statusStyle}`}>
            {node.status}
          </span>
        )}
      </div>
      {node.description && (
        <div className="text-xs text-slate-500 px-3">{node.description}</div>
      )}
      {inputEntries.length > 0 && (
        <div className="flex flex-wrap gap-2 px-3">
          {inputEntries.map(([key, value]) => (
            <span
              key={`${node.id}-${key}`}
              className="rounded-full bg-white/5 px-2 py-0.5 text-xs text-slate-400"
            >
              {key}: {String(value)}
            </span>
          ))}
        </div>
      )}
      {node.children?.length ? (
        <div className="space-y-2">
          {node.children.map((child) => renderNode(child, depth + 1))}
        </div>
      ) : null}
    </div>
  )
}

export function AgenticChat({ selectedDocumentId }: AgenticChatProps) {
  const [prompt, setPrompt] = useState('')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [action, setAction] = useState<ChatAction>('planning')
  const [isVerifying, setIsVerifying] = useState(false)
  const [lastUserRequest, setLastUserRequest] = useState('')
  const [isRunning, setIsRunning] = useState(false)
  const [isExecuting, setIsExecuting] = useState(false)
  const [localDocumentId, setLocalDocumentId] = useState<string | undefined>(
    selectedDocumentId
  )
  const queryClient = useQueryClient()

  useEffect(() => {
    if (selectedDocumentId) {
      setLocalDocumentId(selectedDocumentId)
    }
  }, [selectedDocumentId])

  const { data: documents } = useQuery({
    queryKey: ['documents'],
    queryFn: () => api.getDocuments(),
  })
  const { data: orchestrationSettings } = useQuery({
    queryKey: ['orchestration-settings'],
    queryFn: () => api.getOrchestrationSettings(),
  })

  const activeDocument = useMemo(
    () => documents?.find((doc) => doc.id === localDocumentId),
    [documents, localDocumentId]
  )

  const actionLabel = ACTION_LABELS[action]
  const requiresDocument = action === 'planning'

  const handleSubmit = async () => {
    const trimmed = prompt.trim()
    if (!trimmed || isRunning) return
    if (requiresDocument && !localDocumentId) return

    // Save the request for verification later
    setLastUserRequest(trimmed)

    const userMessage: ChatMessage = {
      id: `msg_${Date.now()}`,
      role: 'user',
      content: trimmed,
      actionLabel,
    }

    setMessages((prev) => [...prev, userMessage])
    setPrompt('')
    setIsRunning(true)

    try {
      if (action === 'planning') {
        const plan = await api.planDocument(localDocumentId!, {
          prompt: trimmed,
        })

        const assistantMessage: ChatMessage = {
          id: `msg_${Date.now()}_plan`,
          role: 'assistant',
          content: plan.orchestration
            ? `Plan generated via ${plan.orchestration.strategy} in ${formatModeLabel(plan.orchestration.final_mode)} mode.`
            : 'Plan generated successfully.',
          actionLabel,
          plan,
          originalRequest: trimmed,
        }

        setMessages((prev) => [...prev, assistantMessage])
      }
    } catch (error) {
      const message =
        error instanceof Error ? error.message : 'Failed to run the request.'
      setMessages((prev) => [
        ...prev,
        { id: `msg_${Date.now()}_error`, role: 'error', content: message },
      ])
    } finally {
      setIsRunning(false)
    }
  }

  const handleVerify = async (originalRequest: string) => {
    if (!localDocumentId || isVerifying) return

    setIsVerifying(true)

    try {
      const result = await api.verifyChanges(localDocumentId, originalRequest)

      const verificationMessage: ChatMessage = {
        id: `msg_${Date.now()}_verification`,
        role: 'verification',
        content: result.verification.summary,
        verificationResult: result.verification,
        originalRequest,
      }

      setMessages((prev) => [...prev, verificationMessage])

    } catch (error) {
      const message =
        error instanceof Error ? error.message : 'Failed to verify changes.'
      setMessages((prev) => [
        ...prev,
        { id: `msg_${Date.now()}_error`, role: 'error', content: message },
      ])
    } finally {
      setIsVerifying(false)
    }
  }

  const handleExecute = async (plan: PlanResponse, messageId: string) => {
    if (!localDocumentId || isExecuting) return

    setIsExecuting(true)

    try {
      const result = await api.executePlan(localDocumentId, plan.tree)

      // Update the plan message's node statuses based on execution result
      setMessages((prev) =>
        prev.map((msg) => {
          if (msg.id !== messageId || !msg.plan) return msg

          // Deep clone the plan to update node statuses
          const updatedTree = JSON.parse(JSON.stringify(msg.plan.tree))

          // Update all nodes to completed/failed based on progress log
          const progressMap = new Map<string, string>()
          for (const log of result.progress || []) {
            if (log.status === 'completed' || log.status === 'failed') {
              progressMap.set(log.node_id, log.status)
            }
          }

          // Recursively update node statuses
          const updateNodeStatus = (nodes: PlanActionNode[]) => {
            for (const node of nodes) {
              const status = progressMap.get(node.id)
              if (status) {
                node.status = status
              } else if (result.success) {
                // If overall success and no specific status, mark as completed
                node.status = 'completed'
              }
              if (node.children?.length) {
                updateNodeStatus(node.children)
              }
            }
          }

          if (updatedTree.tree) {
            updateNodeStatus(updatedTree.tree)
          }

          return {
            ...msg,
            plan: {
              ...msg.plan,
              tree: updatedTree,
            },
          }
        })
      )

      const executionMessage: ChatMessage = {
        id: `msg_${Date.now()}_execution`,
        role: 'execution',
        content: result.success
          ? `Plan executed successfully! ${result.completed}/${result.total} actions completed.`
          : `Plan execution had errors. ${result.completed}/${result.total} actions completed, ${result.failed} failed.`,
        executionResult: {
          success: result.success,
          completed: result.completed,
          failed: result.failed,
          total: result.total,
        },
      }

      setMessages((prev) => [...prev, executionMessage])

      // Refresh documents list to show updated content
      queryClient.invalidateQueries({ queryKey: ['documents'] })

    } catch (error) {
      const message =
        error instanceof Error ? error.message : 'Failed to execute the plan.'
      setMessages((prev) => [
        ...prev,
        { id: `msg_${Date.now()}_error`, role: 'error', content: message },
      ])
    } finally {
      setIsExecuting(false)
    }
  }

  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.02] shadow-sm">
      <div className="border-b border-white/10 px-6 py-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-[#39ff14]" />
              <h3 className="text-lg font-semibold text-white">Agentic Chat</h3>
            </div>
            <p className="text-sm text-slate-500">
              Run document operations as structured agent actions.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <select
              value={action}
              onChange={(event) => setAction(event.target.value as ChatAction)}
              className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-slate-200 focus:outline-none focus:ring-2 focus:ring-[#39ff14]/30"
            >
              <option value="planning">Agentic Planning</option>
            </select>
            <div className="flex items-center gap-2">
              <FileText className="h-4 w-4 text-slate-500" />
              <select
                value={localDocumentId || ''}
                onChange={(event) =>
                  setLocalDocumentId(event.target.value || undefined)
                }
                className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-slate-200 focus:outline-none focus:ring-2 focus:ring-[#39ff14]/30"
              >
                <option value="">Select a document</option>
                {documents?.map((doc) => (
                  <option key={doc.id} value={doc.id}>
                    {doc.title}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>
        {activeDocument && (
          <div className="mt-3 text-xs text-slate-500">
            Active: <span className="font-medium text-slate-200">{activeDocument.title}</span>
            {activeDocument.author ? ` · ${activeDocument.author}` : ''}
          </div>
        )}
        {orchestrationSettings?.settings && (
          <div className="mt-3 rounded-lg border border-indigo-100 bg-indigo-50 px-3 py-2 text-xs text-indigo-900">
            Strategy: <span className="font-semibold">{orchestrationSettings.settings.strategy}</span>
            {orchestrationSettings.settings.allow_orchestrator_takeover
              ? ' · takeover enabled'
              : ' · takeover disabled'}
          </div>
        )}
      </div>

      <div className="flex flex-col gap-4 px-6 py-4">
        <div className="flex items-start gap-3">
          <div className="rounded-full bg-[#39ff14]/10 p-2 text-[#39ff14]">
            <User className="h-4 w-4" />
          </div>
          <div className="flex-1">
            <textarea
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              placeholder="Describe the action you want to plan or execute."
              className="min-h-[96px] w-full resize-y rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-slate-200 focus:outline-none focus:ring-2 focus:ring-[#39ff14]/30"
            />
            <div className="mt-3 flex items-center justify-between">
              <span className="text-xs text-slate-500">
                {requiresDocument && !localDocumentId
                  ? 'Select a document first.'
                  : 'Ready to run.'}
              </span>
              <button
                onClick={handleSubmit}
                disabled={!prompt.trim() || (requiresDocument && !localDocumentId) || isRunning}
                className="inline-flex items-center gap-2 rounded-lg bg-[#39ff14] px-4 py-2 text-sm font-medium text-[#060a14] shadow-sm transition hover:bg-[#39ff14]/90 disabled:cursor-not-allowed disabled:bg-[#39ff14]/30"
              >
                {isRunning ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Running...
                  </>
                ) : (
                  <>
                    <Send className="h-4 w-4" />
                    Run {actionLabel}
                  </>
                )}
              </button>
            </div>
          </div>
        </div>

        <div className="space-y-4">
          {messages.map((message) => (
            <div
              key={message.id}
              className={`rounded-xl border px-4 py-3 ${
                message.role === 'error'
                  ? 'border-red-500/20 bg-red-500/10 text-red-400'
                  : message.role === 'execution'
                  ? message.executionResult?.success
                    ? 'border-green-500/20 bg-green-500/10 text-green-400'
                    : 'border-yellow-500/20 bg-yellow-500/10 text-yellow-400'
                  : message.role === 'verification'
                  ? message.verificationResult?.verified
                    ? 'border-emerald-500/20 bg-emerald-500/10 text-emerald-400'
                    : 'border-amber-500/20 bg-amber-500/10 text-amber-400'
                  : 'border-white/10 bg-white/[0.03] text-white'
              }`}
            >
              <div className="flex items-center gap-2 text-sm font-medium">
                {message.role === 'assistant' ? (
                  <Bot className="h-4 w-4 text-[#39ff14]" />
                ) : message.role === 'execution' ? (
                  message.executionResult?.success ? (
                    <CheckCircle className="h-4 w-4 text-green-400" />
                  ) : (
                    <XCircle className="h-4 w-4 text-yellow-400" />
                  )
                ) : message.role === 'verification' ? (
                  message.verificationResult?.verified ? (
                    <ShieldCheck className="h-4 w-4 text-emerald-400" />
                  ) : (
                    <RefreshCw className="h-4 w-4 text-amber-400" />
                  )
                ) : (
                  <User className="h-4 w-4 text-slate-500" />
                )}
                <span className="capitalize">
                  {message.role === 'execution' ? 'Execution Result' :
                   message.role === 'verification' ? 'Verification' :
                   message.role}
                </span>
                {message.actionLabel && (
                  <span className="rounded-full bg-[#39ff14]/10 px-2 py-0.5 text-xs text-[#39ff14]">
                    {message.actionLabel}
                  </span>
                )}
              </div>
              <p className="mt-2 text-sm">{message.content}</p>

              {message.role === 'execution' && message.executionResult?.success && localDocumentId && (
                <div className="mt-3 space-y-3">
                  <div className="flex flex-wrap gap-2">
                    <button
                      onClick={() => handleVerify(lastUserRequest)}
                      disabled={isVerifying}
                      className="inline-flex items-center gap-2 rounded-lg bg-emerald-500 px-3 py-1.5 text-sm font-medium text-white shadow-sm transition hover:bg-emerald-600 disabled:cursor-not-allowed disabled:bg-emerald-300"
                    >
                      {isVerifying ? (
                        <>
                          <Loader2 className="h-4 w-4 animate-spin" />
                          Verifying...
                        </>
                      ) : (
                        <>
                          <ShieldCheck className="h-4 w-4" />
                          Verify Changes
                        </>
                      )}
                    </button>
                    <button
                      onClick={() => {
                        const url = api.getDownloadUrl(localDocumentId, 'docx')
                        const link = document.createElement('a')
                        link.href = url
                        link.download = `${activeDocument?.title || 'document'}_updated.docx`
                        document.body.appendChild(link)
                        link.click()
                        document.body.removeChild(link)
                      }}
                      className="inline-flex items-center gap-2 rounded-lg bg-blue-500 px-3 py-1.5 text-sm font-medium text-white shadow-sm transition hover:bg-blue-600"
                    >
                      <Download className="h-4 w-4" />
                      Download Updated DOCX
                    </button>
                    <button
                      onClick={() => {
                        const url = api.getDownloadUrl(localDocumentId, 'original')
                        const link = document.createElement('a')
                        link.href = url
                        link.download = `${activeDocument?.title || 'document'}_original.docx`
                        document.body.appendChild(link)
                        link.click()
                        document.body.removeChild(link)
                      }}
                      className="inline-flex items-center gap-2 rounded-lg bg-slate-600 px-3 py-1.5 text-sm font-medium text-white shadow-sm transition hover:bg-slate-500"
                    >
                      <Download className="h-4 w-4" />
                      Download Original
                    </button>
                    <button
                      onClick={() => {
                        const url = api.getDownloadUrl(localDocumentId, 'markdown')
                        const link = document.createElement('a')
                        link.href = url
                        link.download = `${activeDocument?.title || 'document'}.md`
                        document.body.appendChild(link)
                        link.click()
                        document.body.removeChild(link)
                      }}
                      className="inline-flex items-center gap-2 rounded-lg bg-slate-500 px-3 py-1.5 text-sm font-medium text-white shadow-sm transition hover:bg-slate-400"
                    >
                      <Download className="h-4 w-4" />
                      Download Markdown
                    </button>
                  </div>
                </div>
              )}

              {/* Verification Results */}
              {message.role === 'verification' && message.verificationResult && (
                <div className="mt-3 space-y-3">
                  {/* Confidence Badge */}
                  <div className="flex items-center gap-2">
                    <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium ${
                      message.verificationResult.verified
                        ? 'bg-emerald-500/10 text-emerald-400'
                        : 'bg-amber-500/10 text-amber-400'
                    }`}>
                      {message.verificationResult.verified ? (
                        <CheckCircle2 className="h-3 w-3" />
                      ) : (
                        <XCircle className="h-3 w-3" />
                      )}
                      {message.verificationResult.verified ? 'Verified' : 'Needs Attention'}
                    </span>
                    <span className="text-xs text-slate-500">
                      Confidence: {Math.round(message.verificationResult.confidence * 100)}%
                    </span>
                  </div>

                  {/* Findings */}
                  <div className="space-y-2">
                    <div className="text-xs font-semibold text-slate-500 uppercase">Findings</div>
                    {message.verificationResult.findings.map((finding, idx) => (
                      <div
                        key={idx}
                        className={`rounded-lg border p-3 text-sm ${
                          finding.passed
                            ? 'border-green-500/20 bg-green-500/10'
                            : 'border-red-500/20 bg-red-500/10'
                        }`}
                      >
                        <div className="flex items-center gap-2">
                          {finding.passed ? (
                            <CheckCircle className="h-4 w-4 text-green-400 flex-shrink-0" />
                          ) : (
                            <XCircle className="h-4 w-4 text-red-400 flex-shrink-0" />
                          )}
                          <span className={`font-medium ${finding.passed ? 'text-green-400' : 'text-red-400'}`}>
                            {finding.check}
                          </span>
                        </div>
                        <p className={`mt-1 text-xs ${finding.passed ? 'text-green-400' : 'text-red-400'}`}>
                          {finding.details}
                        </p>
                      </div>
                    ))}
                  </div>

                  {/* Suggestions if verification failed */}
                  {!message.verificationResult.verified && message.verificationResult.suggestions && message.verificationResult.suggestions.length > 0 && (
                    <div className="space-y-2">
                      <div className="text-xs font-semibold text-slate-500 uppercase">Suggestions</div>
                      <ul className="list-disc list-inside space-y-1 text-sm text-amber-400">
                        {message.verificationResult.suggestions.map((suggestion, idx) => (
                          <li key={idx}>{suggestion}</li>
                        ))}
                      </ul>
                      <button
                        onClick={() => {
                          setPrompt(message.originalRequest || '')
                        }}
                        className="inline-flex items-center gap-2 rounded-lg bg-amber-500 px-3 py-1.5 text-sm font-medium text-white shadow-sm transition hover:bg-amber-600"
                      >
                        <RefreshCw className="h-4 w-4" />
                        Replan
                      </button>
                    </div>
                  )}
                </div>
              )}

              {message.plan && (
                <div className="mt-4 space-y-4">
                  <div className="rounded-lg border border-[#39ff14]/20 bg-[#39ff14]/10 px-4 py-3 text-sm text-[#39ff14]">
                    <div className="font-medium">{message.plan.plan.title}</div>
                    <div className="mt-1 text-xs text-[#39ff14]">
                      {message.plan.plan.total_actions} actions · {message.plan.plan.chapters} chapters ·{' '}
                      {message.plan.plan.sections} sections · {message.plan.plan.pages} pages
                    </div>
                  </div>

                  <div className="rounded-lg border border-white/10 bg-white/[0.02] p-3">
                    <div className="text-xs font-semibold text-slate-500 uppercase">
                      Plan Tree
                    </div>
                    <pre className="mt-2 whitespace-pre-wrap text-xs text-slate-200">
                      {message.plan.plan.tree_visualization}
                    </pre>
                  </div>

                  <div className="space-y-2">
                    <div className="text-xs font-semibold text-slate-500 uppercase">
                      Actions
                    </div>
                    {message.plan.tree.tree.map((node) => renderNode(node))}
                  </div>

                  {renderOrchestration(message.plan.orchestration)}

                  <div className="mt-4 flex justify-end">
                    <button
                      onClick={() => handleExecute(message.plan!, message.id)}
                      disabled={isExecuting}
                      className="inline-flex items-center gap-2 rounded-lg bg-green-500 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-green-600 disabled:cursor-not-allowed disabled:bg-green-300"
                    >
                      {isExecuting ? (
                        <>
                          <Loader2 className="h-4 w-4 animate-spin" />
                          Executing...
                        </>
                      ) : (
                        <>
                          <Play className="h-4 w-4" />
                          Execute Plan
                        </>
                      )}
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}

          {messages.length === 0 && (
            <div className="rounded-lg border border-dashed border-white/10 px-4 py-6 text-center text-sm text-slate-500">
              No activity yet. Pick an action and send a request to start the chat.
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
