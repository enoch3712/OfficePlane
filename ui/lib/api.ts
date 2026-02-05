import type {
  Document,
  DocumentInstance,
  DocumentListItem,
  ExecutePlanResponse,
  ExecutionHistoryEvent,
  InstanceState,
  Metrics,
  PlanResponse,
  PlanTree,
  Task,
  TaskPriority,
  TaskState,
  VerifyResponse,
} from './types'

type QueryValue = string | number | boolean | null | undefined
type QueryParams = Record<string, QueryValue>

const rawApiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001'
const trimmedApiUrl = rawApiUrl.replace(/\/+$/, '')
const API_BASE = trimmedApiUrl.endsWith('/api')
  ? trimmedApiUrl
  : `${trimmedApiUrl}/api`

const buildUrl = (path: string, query?: QueryParams) => {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  const url = `${API_BASE}${normalizedPath}`

  if (!query) {
    return url
  }

  const searchParams = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== null) {
      searchParams.set(key, String(value))
    }
  }

  const qs = searchParams.toString()
  return qs ? `${url}?${qs}` : url
}

interface RequestOptions extends Omit<RequestInit, 'body'> {
  body?: BodyInit | Record<string, unknown>
  query?: QueryParams
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { body, query, headers, ...init } = options
  const isFormData = typeof FormData !== 'undefined' && body instanceof FormData
  const isBodyObject =
    body !== undefined &&
    body !== null &&
    !isFormData &&
    typeof body === 'object' &&
    !(body instanceof URLSearchParams) &&
    !(body instanceof Blob) &&
    !(body instanceof ArrayBuffer)

  const response = await fetch(buildUrl(path, query), {
    ...init,
    headers: {
      ...(isBodyObject ? { 'Content-Type': 'application/json' } : {}),
      ...(headers || {}),
    },
    body:
      body === undefined
        ? undefined
        : isBodyObject
        ? JSON.stringify(body)
        : (body as BodyInit),
  })

  const raw = await response.text()

  if (!response.ok) {
    let message = `Request failed with status ${response.status}`

    if (raw) {
      try {
        const parsed = JSON.parse(raw) as { detail?: string; message?: string }
        message = parsed.detail || parsed.message || message
      } catch {
        message = raw
      }
    }

    throw new Error(message)
  }

  if (!raw) {
    return undefined as T
  }

  try {
    return JSON.parse(raw) as T
  } catch {
    return raw as T
  }
}

export const api = {
  getDocuments() {
    return request<DocumentListItem[]>('/documents')
  },

  getDocument(documentId: string) {
    return request<Document>(`/documents/${encodeURIComponent(documentId)}`)
  },

  deleteDocument(documentId: string) {
    return request<{ status: string; id: string }>(
      `/documents/${encodeURIComponent(documentId)}`,
      { method: 'DELETE' }
    )
  },

  getDownloadUrl(documentId: string, format: 'original' | 'docx' | 'markdown' | 'md' = 'original') {
    return buildUrl(`/documents/${encodeURIComponent(documentId)}/download`, { format })
  },

  getInstances(state?: InstanceState) {
    return request<DocumentInstance[]>('/instances', {
      query: { state },
    })
  },

  closeInstance(instanceId: string) {
    return request<DocumentInstance>(
      `/instances/${encodeURIComponent(instanceId)}/close`,
      { method: 'POST' }
    )
  },

  deleteInstance(instanceId: string) {
    return request<{ status: string; id: string }>(
      `/instances/${encodeURIComponent(instanceId)}`,
      { method: 'DELETE' }
    )
  },

  getTasks(params: {
    state?: TaskState
    priority?: TaskPriority
    limit?: number
  } = {}) {
    return request<Task[]>('/tasks', { query: params })
  },

  cancelTask(taskId: string) {
    return request<Task>(`/tasks/${encodeURIComponent(taskId)}/cancel`, {
      method: 'POST',
    })
  },

  retryTask(taskId: string) {
    return request<Task>(`/tasks/${encodeURIComponent(taskId)}/retry`, {
      method: 'POST',
    })
  },

  getHistory(params: {
    eventType?: string
    limit?: number
    offset?: number
  } = {}) {
    return request<ExecutionHistoryEvent[]>('/history', { query: params })
  },

  getMetrics() {
    return request<Metrics>('/metrics')
  },

  planDocument(
    documentId: string,
    payload: {
      prompt: string
      max_chapters?: number
      max_sections_per_chapter?: number
      max_pages_per_section?: number
      include_content_outlines?: boolean
    }
  ) {
    return request<PlanResponse>(`/documents/${encodeURIComponent(documentId)}/plan`, {
      method: 'POST',
      body: payload,
    })
  },

  executePlan(documentId: string, tree: PlanTree) {
    return request<ExecutePlanResponse>(`/documents/${encodeURIComponent(documentId)}/execute`, {
      method: 'POST',
      body: { tree },
    })
  },

  verifyChanges(documentId: string, originalRequest: string, expectedChanges?: string[]) {
    return request<VerifyResponse>(`/documents/${encodeURIComponent(documentId)}/verify`, {
      method: 'POST',
      body: {
        original_request: originalRequest,
        expected_changes: expectedChanges,
      },
    })
  },
}

