export enum InstanceState {
  OPENING = 'OPENING',
  OPEN = 'OPEN',
  IDLE = 'IDLE',
  IN_USE = 'IN_USE',
  CLOSING = 'CLOSING',
  CLOSED = 'CLOSED',
  ERROR = 'ERROR',
  CRASHED = 'CRASHED',
}

export enum TaskState {
  QUEUED = 'QUEUED',
  RUNNING = 'RUNNING',
  COMPLETED = 'COMPLETED',
  FAILED = 'FAILED',
  CANCELLED = 'CANCELLED',
  RETRYING = 'RETRYING',
  TIMEOUT = 'TIMEOUT',
}

export enum TaskPriority {
  LOW = 'LOW',
  NORMAL = 'NORMAL',
  HIGH = 'HIGH',
  CRITICAL = 'CRITICAL',
}

export enum EventType {
  INSTANCE_CREATED = 'INSTANCE_CREATED',
  INSTANCE_OPENED = 'INSTANCE_OPENED',
  INSTANCE_USED = 'INSTANCE_USED',
  INSTANCE_CLOSED = 'INSTANCE_CLOSED',
  INSTANCE_ERROR = 'INSTANCE_ERROR',
  INSTANCE_HEARTBEAT = 'INSTANCE_HEARTBEAT',

  TASK_QUEUED = 'TASK_QUEUED',
  TASK_STARTED = 'TASK_STARTED',
  TASK_COMPLETED = 'TASK_COMPLETED',
  TASK_FAILED = 'TASK_FAILED',
  TASK_RETRY = 'TASK_RETRY',
  TASK_CANCELLED = 'TASK_CANCELLED',
  TASK_TIMEOUT = 'TASK_TIMEOUT',

  DOCUMENT_CREATED = 'DOCUMENT_CREATED',
  DOCUMENT_IMPORTED = 'DOCUMENT_IMPORTED',
  DOCUMENT_EXPORTED = 'DOCUMENT_EXPORTED',
  DOCUMENT_EDITED = 'DOCUMENT_EDITED',
  DOCUMENT_DELETED = 'DOCUMENT_DELETED',

  SYSTEM_STARTUP = 'SYSTEM_STARTUP',
  SYSTEM_SHUTDOWN = 'SYSTEM_SHUTDOWN',
  WORKER_STARTED = 'WORKER_STARTED',
  WORKER_STOPPED = 'WORKER_STOPPED',
}

export interface DocumentSection {
  id: string
  title: string
  order_index: number
  page_count: number
}

export interface DocumentChapter {
  id: string
  title: string
  order_index: number
  sections: DocumentSection[]
}

export interface DocumentListItem {
  id: string
  title: string
  author?: string | null
  createdAt?: string
  total_chapters: number
  total_sections: number
  total_pages?: number
}

export interface Document {
  id: string
  title: string
  author?: string | null
  chapters: DocumentChapter[]
  total_chapters: number
  total_pages: number
}

export interface DocumentInstance {
  id: string
  documentId?: string | null
  state: InstanceState
  stateMessage?: string | null
  processPid?: number | null
  hostName?: string | null
  driverType: string
  createdAt?: string
  openedAt?: string | null
  lastUsedAt?: string | null
  closedAt?: string | null
  memoryMb?: number | null
  cpuPercent?: number | null
  filePath?: string | null
  metadata?: Record<string, unknown>
  document?: DocumentListItem | null
}

export interface Task {
  id: string
  taskType: string
  taskName?: string | null
  documentId?: string | null
  instanceId?: string | null
  state: TaskState
  priority: TaskPriority
  maxRetries: number
  retryCount: number
  createdAt: string
  startedAt?: string | null
  completedAt?: string | null
  errorMessage?: string | null
  payload?: Record<string, unknown>
  result?: Record<string, unknown> | null
  document?: DocumentListItem | null
}

export interface ExecutionHistoryEvent {
  id: string
  eventType: EventType
  eventMessage?: string | null
  timestamp: string
  durationMs?: number | null
  actorType?: string | null
  actorId?: string | null
  document?: DocumentListItem | null
  task?: Task | null
  metadata?: Record<string, unknown>
}

export interface WebSocketEvent {
  type: string
  data: Record<string, unknown>
  timestamp: string
}

export type PlanNodeStatus =
  | 'pending'
  | 'ready'
  | 'running'
  | 'completed'
  | 'failed'
  | 'skipped'

export interface PlanActionNode {
  id: string
  action: string
  description: string
  status?: PlanNodeStatus | string
  inputs?: Record<string, unknown>
  children?: PlanActionNode[]
}

export interface PlanSummary {
  plan_id: string
  title: string
  original_prompt: string
  total_actions: number
  chapters: number
  sections: number
  pages: number
  tree_visualization: string
  action_breakdown: Record<string, number>
}

export interface PlanTree {
  id: string
  title: string
  original_prompt: string
  created_at: string
  summary: Record<string, unknown>
  tree: PlanActionNode[]
}

export interface PlanResponse {
  document: {
    id: string
    title: string
    author?: string | null
    chapter_count: number
    section_count: number
    page_count: number
  }
  plan: PlanSummary
  tree: PlanTree
}

export interface ExecuteProgressEntry {
  node_id: string
  action: string
  status: 'running' | 'completed' | 'failed'
  output?: Record<string, unknown>
  error?: string
}

export interface ExecutePlanResponse {
  success: boolean
  completed: number
  failed: number
  total: number
  progress: ExecuteProgressEntry[]
  errors?: Record<string, unknown>
}

export interface VerificationFinding {
  check: string
  passed: boolean
  details: string
}

export interface VerificationResult {
  verified: boolean
  confidence: number
  findings: VerificationFinding[]
  summary: string
  suggestions?: string[]
  raw_response?: string
}

export interface VerifyResponse {
  document_id: string
  document_title: string
  original_request: string
  verification: VerificationResult
  document_stats: {
    chapters: number
    sections: number
    pages: number
  }
}

export interface Metrics {
  instances: {
    total: number
    byState: Record<string, number>
  }
  tasks: {
    total: number
    byState: Record<string, number>
    avgDurationMs: number
    failureRate: number
  }
  system: {
    uptime: number
    memoryUsageMb: number
    cpuPercent: number
  }
}

export interface OrchestrationSummary {
  strategy: string
  initial_mode: string
  final_mode: string
  worker_attempts: number
  worker_confidence?: number | null
  takeover_reason?: string | null
  signals?: Record<string, unknown>
}

