export interface GenerateDocxInput {
  source_document_ids: string[]
  brief: string
  style?: string
  audience?: string
  target_length?: 'short' | 'medium' | 'long'
}

export interface GeneratePptxInput {
  source_document_ids: string[]
  brief: string
  slide_count?: number
  style?: string
  audience?: string
  tone?: string
}

export interface DocumentEditInput {
  workspace_id: string
  operation: 'insert_after' | 'insert_before' | 'insert_as_child' | 'replace' | 'delete'
  anchor_id?: string
  target_id?: string
  parent_id?: string
  position?: number
  node?: Record<string, unknown>
}

export interface GenerateDocxResult {
  file_path: string
  file_url: string
  title: string
  node_count: number
  model: string
  source_document_ids: string[]
}

export interface GeneratePptxResult {
  file_path: string
  file_url: string
  title: string
  slide_count: number
  model: string
  source_document_ids: string[]
}

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001'

export async function generateDocx(input: GenerateDocxInput): Promise<GenerateDocxResult> {
  const r = await fetch(`${API}/api/jobs/invoke/generate-docx`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ inputs: input }),
  })
  if (!r.ok) throw new Error(`generate-docx failed: ${r.status}`)
  const j = await r.json()
  return j.output
}

export async function generatePptx(input: GeneratePptxInput): Promise<GeneratePptxResult> {
  const r = await fetch(`${API}/api/jobs/invoke/generate-pptx`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ inputs: input }),
  })
  if (!r.ok) throw new Error(`generate-pptx failed: ${r.status}`)
  const j = await r.json()
  return j.output
}

export async function applyEdit(
  input: DocumentEditInput,
): Promise<{ operation: string; affected_node_id: string; revision: number }> {
  const r = await fetch(`${API}/api/jobs/invoke/document-edit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ inputs: input }),
  })
  if (!r.ok) throw new Error(`document-edit failed: ${r.status}`)
  const j = await r.json()
  return j.output
}
