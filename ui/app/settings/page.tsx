'use client'

import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { OrchestrationSettings } from '@/lib/types'
import { useWebSocket } from '@/hooks/useWebSocket'
import {
  Bell,
  HelpCircle,
  Save,
  Settings,
  ShieldCheck,
  SlidersHorizontal,
  Workflow,
} from 'lucide-react'

const defaultSettings: OrchestrationSettings = {
  enabled: true,
  strategy: 'workchestrator',
  allow_orchestrator_takeover: true,
  worker: {
    provider: 'auto',
    model: '',
  },
  orchestrator: {
    provider: 'auto',
    model: '',
  },
  takeover: {
    worker_confidence_threshold: 0.68,
    max_worker_retries: 1,
    complexity_takeover_threshold: 0.72,
    max_validation_issues: 1,
  },
}

export default function SettingsPage() {
  const { status } = useWebSocket()
  const queryClient = useQueryClient()
  const [draft, setDraft] = useState<OrchestrationSettings>(defaultSettings)
  const [hasLocalEdits, setHasLocalEdits] = useState(false)

  const { data, isLoading } = useQuery({
    queryKey: ['orchestration-settings'],
    queryFn: () => api.getOrchestrationSettings(),
  })

  useEffect(() => {
    if (data?.settings) {
      setDraft(data.settings)
      setHasLocalEdits(false)
    }
  }, [data])

  const saveMutation = useMutation({
    mutationFn: (settings: OrchestrationSettings) =>
      api.updateOrchestrationSettings(settings),
    onSuccess: ({ settings }) => {
      setDraft(settings)
      setHasLocalEdits(false)
      queryClient.invalidateQueries({ queryKey: ['orchestration-settings'] })
    },
  })

  const updateDraft = (updater: (current: OrchestrationSettings) => OrchestrationSettings) => {
    setDraft((current) => {
      const next = updater(current)
      setHasLocalEdits(true)
      return next
    })
  }

  return (
    <div className="h-screen flex flex-col bg-gray-50">
      <header className="h-16 bg-white border-b border-gray-200 flex items-center justify-between px-6">
        <div className="flex items-center gap-4">
          <h1 className="text-xl font-semibold text-gray-900">Settings</h1>
          <div className="flex items-center gap-2">
            <div
              className={`w-2 h-2 rounded-full ${
                status === 'connected' ? 'bg-green-500' : 'bg-gray-300'
              }`}
            />
            <span className="text-sm text-gray-600">
              {status === 'connected' ? 'Live' : 'Disconnected'}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <button className="p-2 hover:bg-gray-100 rounded-lg transition-colors">
            <HelpCircle className="w-5 h-5 text-gray-600" />
          </button>
          <button className="p-2 hover:bg-gray-100 rounded-lg transition-colors relative">
            <Bell className="w-5 h-5 text-gray-600" />
            <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-orange-500 rounded-full" />
          </button>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-5xl mx-auto space-y-6">
          <div className="bg-white border border-gray-200 rounded-xl p-6">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 rounded-lg bg-orange-50 flex items-center justify-center">
                  <Settings className="w-5 h-5 text-orange-600" />
                </div>
                <div>
                  <h2 className="text-lg font-semibold text-gray-900">Agentic Planning</h2>
                  <p className="text-sm text-gray-500">
                    Configure how OfficePlane routes document requests between a worker planner and orchestrator takeover.
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-3">
                {saveMutation.isSuccess && !hasLocalEdits && (
                  <span className="text-xs text-emerald-600">Saved</span>
                )}
                {saveMutation.isError && (
                  <span className="text-xs text-red-600">
                    {saveMutation.error instanceof Error
                      ? saveMutation.error.message
                      : 'Failed to save settings.'}
                  </span>
                )}
                <button
                  onClick={() => saveMutation.mutate(draft)}
                  disabled={saveMutation.isPending || !hasLocalEdits}
                  className="inline-flex items-center gap-2 rounded-lg bg-orange-500 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-orange-600 disabled:cursor-not-allowed disabled:bg-orange-300"
                >
                  <Save className="w-4 h-4" />
                  {saveMutation.isPending ? 'Saving...' : 'Save Settings'}
                </button>
              </div>
            </div>
          </div>

          <div className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
            <div className="space-y-6">
              <div className="bg-white border border-gray-200 rounded-xl p-6">
                <div className="flex items-center gap-2">
                  <Workflow className="w-4 h-4 text-indigo-600" />
                  <h3 className="text-base font-semibold text-gray-900">Routing Mode</h3>
                </div>

                <div className="mt-5 grid gap-4 md:grid-cols-2">
                  <label className="rounded-xl border border-gray-200 p-4">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <div className="text-sm font-medium text-gray-900">Enable orchestration</div>
                        <div className="text-xs text-gray-500">
                          Use explicit routing and review instead of a single-pass planner.
                        </div>
                      </div>
                      <input
                        type="checkbox"
                        checked={draft.enabled}
                        onChange={(event) =>
                          updateDraft((current) => ({
                            ...current,
                            enabled: event.target.checked,
                          }))
                        }
                        className="h-4 w-4 rounded border-gray-300 text-orange-500 focus:ring-orange-500"
                      />
                    </div>
                  </label>

                  <label className="rounded-xl border border-gray-200 p-4">
                    <div className="text-sm font-medium text-gray-900">Planning strategy</div>
                    <div className="mt-1 text-xs text-gray-500">
                      `workchestrator` adds explicit delegate/review/takeover transitions.
                    </div>
                    <select
                      value={draft.strategy}
                      onChange={(event) =>
                        updateDraft((current) => ({
                          ...current,
                          strategy: event.target.value as OrchestrationSettings['strategy'],
                        }))
                      }
                      className="mt-3 w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-orange-500"
                    >
                      <option value="workchestrator">Workchestrator</option>
                      <option value="classic">Classic planner</option>
                    </select>
                  </label>
                </div>

                <label className="mt-4 block rounded-xl border border-gray-200 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <div className="text-sm font-medium text-gray-900">Allow orchestrator takeover</div>
                      <div className="text-xs text-gray-500">
                        If the worker plan is weak or risky, the orchestrator replans directly.
                      </div>
                    </div>
                    <input
                      type="checkbox"
                      checked={draft.allow_orchestrator_takeover}
                      onChange={(event) =>
                        updateDraft((current) => ({
                          ...current,
                          allow_orchestrator_takeover: event.target.checked,
                        }))
                      }
                      className="h-4 w-4 rounded border-gray-300 text-orange-500 focus:ring-orange-500"
                    />
                  </div>
                </label>
              </div>

              <div className="bg-white border border-gray-200 rounded-xl p-6">
                <div className="flex items-center gap-2">
                  <SlidersHorizontal className="w-4 h-4 text-indigo-600" />
                  <h3 className="text-base font-semibold text-gray-900">Role Models</h3>
                </div>

                <div className="mt-5 grid gap-4 md:grid-cols-2">
                  <div className="rounded-xl border border-gray-200 p-4">
                    <div className="text-sm font-medium text-gray-900">Worker</div>
                    <div className="mt-1 text-xs text-gray-500">
                      Cheap bounded planner used first when delegation is safe.
                    </div>
                    <select
                      value={draft.worker.provider}
                      onChange={(event) =>
                        updateDraft((current) => ({
                          ...current,
                          worker: {
                            ...current.worker,
                            provider: event.target.value as OrchestrationSettings['worker']['provider'],
                          },
                        }))
                      }
                      className="mt-3 w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-orange-500"
                    >
                      <option value="auto">Auto</option>
                      <option value="gemini">Gemini</option>
                      <option value="openai">OpenAI</option>
                      <option value="mock">Mock</option>
                    </select>
                    <input
                      type="text"
                      value={draft.worker.model || ''}
                      onChange={(event) =>
                        updateDraft((current) => ({
                          ...current,
                          worker: {
                            ...current.worker,
                            model: event.target.value,
                          },
                        }))
                      }
                      placeholder="Optional model override"
                      className="mt-3 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-orange-500"
                    />
                  </div>

                  <div className="rounded-xl border border-gray-200 p-4">
                    <div className="text-sm font-medium text-gray-900">Orchestrator</div>
                    <div className="mt-1 text-xs text-gray-500">
                      Backup planner for cross-cutting edits, retries, and takeover.
                    </div>
                    <select
                      value={draft.orchestrator.provider}
                      onChange={(event) =>
                        updateDraft((current) => ({
                          ...current,
                          orchestrator: {
                            ...current.orchestrator,
                            provider: event.target.value as OrchestrationSettings['orchestrator']['provider'],
                          },
                        }))
                      }
                      className="mt-3 w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-orange-500"
                    >
                      <option value="auto">Auto</option>
                      <option value="gemini">Gemini</option>
                      <option value="openai">OpenAI</option>
                      <option value="mock">Mock</option>
                    </select>
                    <input
                      type="text"
                      value={draft.orchestrator.model || ''}
                      onChange={(event) =>
                        updateDraft((current) => ({
                          ...current,
                          orchestrator: {
                            ...current.orchestrator,
                            model: event.target.value,
                          },
                        }))
                      }
                      placeholder="Optional model override"
                      className="mt-3 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-orange-500"
                    />
                  </div>
                </div>
              </div>
            </div>

            <div className="space-y-6">
              <div className="bg-white border border-gray-200 rounded-xl p-6">
                <div className="flex items-center gap-2">
                  <ShieldCheck className="w-4 h-4 text-indigo-600" />
                  <h3 className="text-base font-semibold text-gray-900">Takeover Policy</h3>
                </div>

                <div className="mt-5 space-y-5">
                  <label className="block">
                    <div className="flex items-center justify-between text-sm font-medium text-gray-900">
                      <span>Worker confidence threshold</span>
                      <span>{draft.takeover.worker_confidence_threshold.toFixed(2)}</span>
                    </div>
                    <input
                      type="range"
                      min="0"
                      max="1"
                      step="0.01"
                      value={draft.takeover.worker_confidence_threshold}
                      onChange={(event) =>
                        updateDraft((current) => ({
                          ...current,
                          takeover: {
                            ...current.takeover,
                            worker_confidence_threshold: Number(event.target.value),
                          },
                        }))
                      }
                      className="mt-2 w-full accent-orange-500"
                    />
                  </label>

                  <label className="block">
                    <div className="flex items-center justify-between text-sm font-medium text-gray-900">
                      <span>Complexity takeover threshold</span>
                      <span>{draft.takeover.complexity_takeover_threshold.toFixed(2)}</span>
                    </div>
                    <input
                      type="range"
                      min="0"
                      max="1"
                      step="0.01"
                      value={draft.takeover.complexity_takeover_threshold}
                      onChange={(event) =>
                        updateDraft((current) => ({
                          ...current,
                          takeover: {
                            ...current.takeover,
                            complexity_takeover_threshold: Number(event.target.value),
                          },
                        }))
                      }
                      className="mt-2 w-full accent-orange-500"
                    />
                  </label>

                  <label className="block">
                    <div className="text-sm font-medium text-gray-900">Max worker retries</div>
                    <input
                      type="number"
                      min={0}
                      max={3}
                      value={draft.takeover.max_worker_retries}
                      onChange={(event) =>
                        updateDraft((current) => ({
                          ...current,
                          takeover: {
                            ...current.takeover,
                            max_worker_retries: Number(event.target.value),
                          },
                        }))
                      }
                      className="mt-2 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-orange-500"
                    />
                  </label>

                  <label className="block">
                    <div className="text-sm font-medium text-gray-900">Max validation issues before takeover</div>
                    <input
                      type="number"
                      min={0}
                      max={10}
                      value={draft.takeover.max_validation_issues}
                      onChange={(event) =>
                        updateDraft((current) => ({
                          ...current,
                          takeover: {
                            ...current.takeover,
                            max_validation_issues: Number(event.target.value),
                          },
                        }))
                      }
                      className="mt-2 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-orange-500"
                    />
                  </label>
                </div>
              </div>

              <div className="bg-slate-900 text-slate-100 rounded-xl p-6">
                <div className="text-sm font-semibold">Current behavior</div>
                <div className="mt-3 text-sm text-slate-300">
                  {isLoading
                    ? 'Loading saved settings...'
                    : draft.enabled
                    ? `${draft.strategy} is active. Worker requests fall back to the orchestrator when confidence drops below ${draft.takeover.worker_confidence_threshold.toFixed(2)} or complexity exceeds ${draft.takeover.complexity_takeover_threshold.toFixed(2)}.`
                    : 'Orchestration is disabled. OfficePlane will use the classic single-pass planner.'}
                </div>
                <div className="mt-4 text-xs text-slate-400">
                  These settings are used by the document chat and included in the orchestration log returned with each plan.
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
