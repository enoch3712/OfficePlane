'use client'

import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { PlanActionNode, PlanResponse } from '@/lib/types'
import { Bot, FileText, Loader2, Send, Sparkles, User } from 'lucide-react'

type ChatAction = 'planning'

interface AgenticChatProps {
  selectedDocumentId?: string
}

type ChatMessage = {
  id: string
  role: 'user' | 'assistant' | 'error'
  content: string
  actionLabel?: string
  plan?: PlanResponse
}

const ACTION_LABELS: Record<ChatAction, string> = {
  planning: 'Agentic Planning',
}

const formatActionLabel = (node: PlanActionNode) => {
  const title = node.inputs?.title ? `: ${node.inputs.title}` : ''
  return `${node.action}${title}`
}

const renderNode = (node: PlanActionNode, depth = 0) => {
  const inputEntries = Object.entries(node.inputs || {}).filter(
    ([key, value]) => key !== 'content' && key !== 'content_outline' && value !== undefined
  )

  return (
    <div key={node.id} className="space-y-2" style={{ marginLeft: depth * 12 }}>
      <div className="flex items-center gap-2 rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm">
        <span className="font-medium text-gray-800">{formatActionLabel(node)}</span>
        {node.status && (
          <span className="ml-auto rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-600">
            {node.status}
          </span>
        )}
      </div>
      {node.description && (
        <div className="text-xs text-gray-500 px-3">{node.description}</div>
      )}
      {inputEntries.length > 0 && (
        <div className="flex flex-wrap gap-2 px-3">
          {inputEntries.map(([key, value]) => (
            <span
              key={`${node.id}-${key}`}
              className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-600"
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
  const [isRunning, setIsRunning] = useState(false)
  const [localDocumentId, setLocalDocumentId] = useState<string | undefined>(
    selectedDocumentId
  )

  useEffect(() => {
    if (selectedDocumentId) {
      setLocalDocumentId(selectedDocumentId)
    }
  }, [selectedDocumentId])

  const { data: documents } = useQuery({
    queryKey: ['documents'],
    queryFn: () => api.getDocuments(),
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
          content: 'Plan generated successfully.',
          actionLabel,
          plan,
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

  return (
    <div className="rounded-xl border border-gray-200 bg-white shadow-sm">
      <div className="border-b border-gray-200 px-6 py-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-orange-500" />
              <h3 className="text-lg font-semibold text-gray-900">Agentic Chat</h3>
            </div>
            <p className="text-sm text-gray-500">
              Run document operations as structured agent actions.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <select
              value={action}
              onChange={(event) => setAction(event.target.value as ChatAction)}
              className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-orange-500"
            >
              <option value="planning">Agentic Planning</option>
            </select>
            <div className="flex items-center gap-2">
              <FileText className="h-4 w-4 text-gray-400" />
              <select
                value={localDocumentId || ''}
                onChange={(event) =>
                  setLocalDocumentId(event.target.value || undefined)
                }
                className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-orange-500"
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
          <div className="mt-3 text-xs text-gray-500">
            Active: <span className="font-medium text-gray-700">{activeDocument.title}</span>
            {activeDocument.author ? ` · ${activeDocument.author}` : ''}
          </div>
        )}
      </div>

      <div className="flex flex-col gap-4 px-6 py-4">
        <div className="flex items-start gap-3">
          <div className="rounded-full bg-orange-100 p-2 text-orange-600">
            <User className="h-4 w-4" />
          </div>
          <div className="flex-1">
            <textarea
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              placeholder="Describe the action you want to plan or execute."
              className="min-h-[96px] w-full resize-y rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-orange-500"
            />
            <div className="mt-3 flex items-center justify-between">
              <span className="text-xs text-gray-400">
                {requiresDocument && !localDocumentId
                  ? 'Select a document first.'
                  : 'Ready to run.'}
              </span>
              <button
                onClick={handleSubmit}
                disabled={!prompt.trim() || (requiresDocument && !localDocumentId) || isRunning}
                className="inline-flex items-center gap-2 rounded-lg bg-orange-500 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-orange-600 disabled:cursor-not-allowed disabled:bg-orange-300"
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
                  ? 'border-red-200 bg-red-50 text-red-700'
                  : 'border-gray-200 bg-gray-50 text-gray-800'
              }`}
            >
              <div className="flex items-center gap-2 text-sm font-medium">
                {message.role === 'assistant' ? (
                  <Bot className="h-4 w-4 text-orange-500" />
                ) : (
                  <User className="h-4 w-4 text-gray-500" />
                )}
                <span className="capitalize">{message.role}</span>
                {message.actionLabel && (
                  <span className="rounded-full bg-orange-100 px-2 py-0.5 text-xs text-orange-600">
                    {message.actionLabel}
                  </span>
                )}
              </div>
              <p className="mt-2 text-sm">{message.content}</p>

              {message.plan && (
                <div className="mt-4 space-y-4">
                  <div className="rounded-lg border border-orange-100 bg-orange-50 px-4 py-3 text-sm text-orange-700">
                    <div className="font-medium">{message.plan.plan.title}</div>
                    <div className="mt-1 text-xs text-orange-600">
                      {message.plan.plan.total_actions} actions · {message.plan.plan.chapters} chapters ·{' '}
                      {message.plan.plan.sections} sections · {message.plan.plan.pages} pages
                    </div>
                  </div>

                  <div className="rounded-lg border border-gray-200 bg-white p-3">
                    <div className="text-xs font-semibold text-gray-500 uppercase">
                      Plan Tree
                    </div>
                    <pre className="mt-2 whitespace-pre-wrap text-xs text-gray-700">
                      {message.plan.plan.tree_visualization}
                    </pre>
                  </div>

                  <div className="space-y-2">
                    <div className="text-xs font-semibold text-gray-500 uppercase">
                      Actions
                    </div>
                    {message.plan.tree.tree.map((node) => renderNode(node))}
                  </div>
                </div>
              )}
            </div>
          ))}

          {messages.length === 0 && (
            <div className="rounded-lg border border-dashed border-gray-200 px-4 py-6 text-center text-sm text-gray-400">
              No activity yet. Pick an action and send a request to start the chat.
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
