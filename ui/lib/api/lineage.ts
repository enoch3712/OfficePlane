import type { LineageResponse } from '@/lib/types'

export async function fetchLineage(documentId: string): Promise<LineageResponse> {
  const res = await fetch(`/api/documents/${documentId}/lineage`, { cache: 'no-store' })
  if (res.status === 404) {
    return mockLineage(documentId)
  }
  if (!res.ok) throw new Error(`Lineage fetch failed: ${res.status}`)
  return res.json() as Promise<LineageResponse>
}

function mockLineage(documentId: string): LineageResponse {
  return {
    document: {
      id: documentId,
      title: 'Home BP Primer (mock)',
      workspace_id: 'ws-mock',
      output_path: '/data/workspaces/mock/output.docx',
    },
    nodes: [
      { id: 's1', type: 'section', label: 'Introduction', parent_id: null },
      { id: 'p1', type: 'paragraph', label: 'BP measurement matters.', parent_id: 's1' },
      { id: 's2', type: 'section', label: 'Method', parent_id: null },
      { id: 'p2', type: 'paragraph', label: 'Pick correct cuff size.', parent_id: 's2' },
      { id: 'p3', type: 'paragraph', label: 'Position arm at heart level.', parent_id: 's2' },
    ],
    sources: [
      {
        id: 'src-bp',
        title: 'Measuring Blood Pressure Checklist',
        chapters: [
          {
            id: 'ch1',
            title: 'Measuring BP',
            sections: [
              { id: 'sec-prep', title: 'Prepare the Patient' },
              { id: 'sec-equip', title: 'Proper Equipment' },
              { id: 'sec-tech', title: 'Proper Technique' },
            ],
          },
        ],
      },
    ],
    derivations: [
      {
        id: 'd1',
        generated_node_id: 'p1',
        source_document_id: 'src-bp',
        source_section_id: 'sec-prep',
        page_numbers: [1],
        text_excerpt: 'Hypertension is a leading cause...',
        skill: 'generate-docx',
        model: 'deepseek/deepseek-v4-flash',
        confidence: 0.91,
        created_at: new Date().toISOString(),
      },
      {
        id: 'd2',
        generated_node_id: 'p2',
        source_document_id: 'src-bp',
        source_section_id: 'sec-equip',
        page_numbers: [2],
        text_excerpt: 'Cuff size matters for accuracy.',
        skill: 'generate-docx',
        model: 'deepseek/deepseek-v4-flash',
        confidence: 0.86,
        created_at: new Date().toISOString(),
      },
      {
        id: 'd3',
        generated_node_id: 'p3',
        source_document_id: 'src-bp',
        source_section_id: 'sec-tech',
        page_numbers: [3],
        text_excerpt: 'Arm at heart level reduces error.',
        skill: 'generate-docx',
        model: 'deepseek/deepseek-v4-flash',
        confidence: 0.88,
        created_at: new Date().toISOString(),
      },
    ],
    revisions: [
      {
        id: 'r1',
        parent_revision_id: null,
        revision_number: 1,
        op: 'create',
        payload: { title: 'Initial generation' },
        actor: 'system',
        created_at: new Date().toISOString(),
      },
      {
        id: 'r2',
        parent_revision_id: 'r1',
        revision_number: 2,
        op: 'replace',
        payload: { node_id: 'p2', reason: 'tighten phrasing' },
        actor: 'user-1',
        created_at: new Date().toISOString(),
      },
      {
        id: 'r3',
        parent_revision_id: 'r2',
        revision_number: 3,
        op: 'insert_after',
        payload: { anchor_id: 'p2', node_id: 'p3' },
        actor: 'user-1',
        created_at: new Date().toISOString(),
      },
    ],
  }
}
