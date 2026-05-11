'use client'

import 'reactflow/dist/style.css'

import { useCallback, useEffect, useMemo, useState } from 'react'
import ReactFlow, {
  Background,
  BackgroundVariant,
  Controls,
  MarkerType,
  MiniMap,
  type Edge,
  type Node,
  useEdgesState,
  useNodesState,
  useReactFlow,
} from 'reactflow'
import { Badge } from '@/components/ui/badge'
import { NodeBadge, type NodeBadgeData } from './NodeBadge'
import { fetchLineage } from '@/lib/api/lineage'
import type {
  LineageDerivation,
  LineageDocumentNode,
  LineageResponse,
  LineageRevision,
  LineageSource,
} from '@/lib/types'
import { cn } from '@/lib/cn'

// ─── Column X positions ───────────────────────────────────────────────────────
const COL_SOURCE = 0
const COL_GENERATED = 600
const COL_REVISION = 1200
const ROW_GAP = 80

// ─── Custom node types ────────────────────────────────────────────────────────
const nodeTypes = { nodeBadge: NodeBadge }

// ─── Helpers ──────────────────────────────────────────────────────────────────
function buildSourceNodes(sources: LineageSource[]): Node<NodeBadgeData>[] {
  const nodes: Node<NodeBadgeData>[] = []
  let y = 0
  for (const src of sources) {
    nodes.push({
      id: `src-doc-${src.id}`,
      type: 'nodeBadge',
      position: { x: COL_SOURCE, y },
      data: { label: src.title, nodeType: 'document', column: 'source' },
    })
    y += ROW_GAP
    for (const ch of src.chapters) {
      nodes.push({
        id: `src-ch-${ch.id}`,
        type: 'nodeBadge',
        position: { x: COL_SOURCE + 20, y },
        data: { label: ch.title, nodeType: 'chapter', column: 'source' },
      })
      y += ROW_GAP
      for (const sec of ch.sections) {
        nodes.push({
          id: `src-sec-${sec.id}`,
          type: 'nodeBadge',
          position: { x: COL_SOURCE + 40, y },
          data: { label: sec.title, nodeType: 'source_section', column: 'source' },
        })
        y += ROW_GAP
      }
    }
  }
  return nodes
}

function buildGeneratedNodes(
  docNodes: LineageDocumentNode[],
  derivations: LineageDerivation[],
): Node<NodeBadgeData>[] {
  // Map node_id → max confidence from derivations
  const confidenceMap = new Map<string, number>()
  for (const d of derivations) {
    if (d.confidence !== undefined) {
      const prev = confidenceMap.get(d.generated_node_id) ?? 0
      if (d.confidence > prev) confidenceMap.set(d.generated_node_id, d.confidence)
    }
  }

  // Build y positions: roots first, then children grouped under parent
  const nodes: Node<NodeBadgeData>[] = []
  let y = 0

  // Sort: roots first
  const roots = docNodes.filter((n) => n.parent_id === null)
  const childMap = new Map<string, LineageDocumentNode[]>()
  for (const n of docNodes) {
    if (n.parent_id) {
      const arr = childMap.get(n.parent_id) ?? []
      arr.push(n)
      childMap.set(n.parent_id, arr)
    }
  }

  function addNode(n: LineageDocumentNode, indent: number) {
    nodes.push({
      id: `gen-${n.id}`,
      type: 'nodeBadge',
      position: { x: COL_GENERATED + indent * 20, y },
      data: {
        label: n.label,
        nodeType: n.type,
        column: 'generated',
        confidence: confidenceMap.get(n.id),
      },
    })
    y += ROW_GAP
    for (const child of childMap.get(n.id) ?? []) {
      addNode(child, indent + 1)
    }
  }

  for (const root of roots) addNode(root, 0)
  return nodes
}

function buildRevisionNodes(revisions: LineageRevision[]): Node<NodeBadgeData>[] {
  const nodes: Node<NodeBadgeData>[] = []
  const sorted = [...revisions].sort((a, b) => a.revision_number - b.revision_number)
  let y = 0
  for (const rev of sorted) {
    nodes.push({
      id: `rev-${rev.id}`,
      type: 'nodeBadge',
      position: { x: COL_REVISION, y },
      data: {
        label: `Rev #${rev.revision_number}`,
        nodeType: 'revision',
        column: 'revision',
        op: rev.op,
        revisionNumber: rev.revision_number,
        actor: rev.actor,
      },
    })
    y += ROW_GAP
  }
  return nodes
}

function buildEdges(data: LineageResponse): Edge[] {
  const edges: Edge[] = []

  // Source hierarchy edges (within source column)
  for (const src of data.sources) {
    for (const ch of src.chapters) {
      edges.push({
        id: `e-src-doc-ch-${ch.id}`,
        source: `src-doc-${src.id}`,
        target: `src-ch-${ch.id}`,
        type: 'smoothstep',
        style: { stroke: '#374151', strokeWidth: 1 },
        animated: false,
      })
      for (const sec of ch.sections) {
        edges.push({
          id: `e-src-ch-sec-${sec.id}`,
          source: `src-ch-${ch.id}`,
          target: `src-sec-${sec.id}`,
          type: 'smoothstep',
          style: { stroke: '#374151', strokeWidth: 1 },
          animated: false,
        })
      }
    }
  }

  // Generated document hierarchy edges
  for (const node of data.nodes) {
    if (node.parent_id) {
      edges.push({
        id: `e-gen-${node.parent_id}-${node.id}`,
        source: `gen-${node.parent_id}`,
        target: `gen-${node.id}`,
        type: 'smoothstep',
        style: { stroke: '#4B5563', strokeWidth: 1 },
      })
    }
  }

  // Derivation edges: source-section → generated node
  for (const d of data.derivations) {
    const sourceId = d.source_section_id
      ? `src-sec-${d.source_section_id}`
      : d.source_chapter_id
        ? `src-ch-${d.source_chapter_id}`
        : `src-doc-${d.source_document_id}`

    edges.push({
      id: `e-deriv-${d.id}`,
      source: sourceId,
      target: `gen-${d.generated_node_id}`,
      type: 'smoothstep',
      animated: true,
      style: { stroke: '#5EFCAB', strokeWidth: 1.5, strokeDasharray: '6 3' },
      markerEnd: { type: MarkerType.ArrowClosed, color: '#5EFCAB' },
      data: {
        derivationId: d.id,
        text_excerpt: d.text_excerpt,
        confidence: d.confidence,
        page_numbers: d.page_numbers,
        generated_node_id: d.generated_node_id,
      },
      label: d.confidence !== undefined ? `${(d.confidence * 100).toFixed(0)}%` : undefined,
      labelStyle: { fill: '#5EFCAB', fontSize: 9, fontFamily: 'monospace' },
      labelBgStyle: { fill: '#0F1116', fillOpacity: 0.8 },
    })
  }

  // Revision parent→child edges
  for (const rev of data.revisions) {
    if (rev.parent_revision_id) {
      edges.push({
        id: `e-rev-${rev.id}`,
        source: `rev-${rev.parent_revision_id}`,
        target: `rev-${rev.id}`,
        type: 'smoothstep',
        style: { stroke: '#9CA3AF', strokeWidth: 1.5 },
        markerEnd: { type: MarkerType.ArrowClosed, color: '#9CA3AF' },
      })
    }
  }

  return edges
}

// ─── Tooltip component ────────────────────────────────────────────────────────
interface TooltipState {
  x: number
  y: number
  text_excerpt?: string
  confidence?: number
  page_numbers?: number[]
}

// ─── Column toggle toolbar ────────────────────────────────────────────────────
interface ColumnToggleProps {
  showSources: boolean
  showGenerated: boolean
  showRevisions: boolean
  onToggle: (col: 'sources' | 'generated' | 'revisions') => void
  onReset: () => void
  selectedNodeId: string | null
}

function ColumnToolbar({
  showSources,
  showGenerated,
  showRevisions,
  onToggle,
  onReset,
  selectedNodeId,
}: ColumnToggleProps) {
  const cols = [
    { key: 'sources' as const, label: 'Sources', active: showSources },
    { key: 'generated' as const, label: 'Generated', active: showGenerated },
    { key: 'revisions' as const, label: 'Revisions', active: showRevisions },
  ]

  return (
    <div className="absolute top-3 left-3 z-10 flex items-center gap-2">
      {cols.map((col) => (
        <button
          key={col.key}
          onClick={() => onToggle(col.key)}
          className={cn(
            'px-3 py-1.5 rounded text-xs font-mono uppercase tracking-wider border transition-colors',
            col.active
              ? 'bg-[#5EFCAB]/15 border-[#5EFCAB]/40 text-[#5EFCAB]'
              : 'bg-[#1C1F26] border-[#374151] text-[#6B7280] hover:border-[#5EFCAB]/30',
          )}
        >
          {col.label}
        </button>
      ))}
      {selectedNodeId && (
        <button
          onClick={onReset}
          className="px-3 py-1.5 rounded text-xs font-mono uppercase tracking-wider border border-[#374151] text-[#9CA3AF] hover:border-[#5EFCAB]/30 bg-[#1C1F26] transition-colors"
        >
          Reset
        </button>
      )}
    </div>
  )
}

// ─── Main graph inner (needs ReactFlow context) ───────────────────────────────
interface GraphInnerProps {
  lineage: LineageResponse
}

function GraphInner({ lineage }: GraphInnerProps) {
  const [showSources, setShowSources] = useState(true)
  const [showGenerated, setShowGenerated] = useState(true)
  const [showRevisions, setShowRevisions] = useState(true)
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
  const [tooltip, setTooltip] = useState<TooltipState | null>(null)

  const { fitView } = useReactFlow()

  // Build base nodes and edges once
  const allBaseNodes = useMemo(() => {
    const sourceNodes = buildSourceNodes(lineage.sources)
    const generatedNodes = buildGeneratedNodes(lineage.nodes, lineage.derivations)
    const revisionNodes = buildRevisionNodes(lineage.revisions)
    return [...sourceNodes, ...generatedNodes, ...revisionNodes]
  }, [lineage])

  const allBaseEdges = useMemo(() => buildEdges(lineage), [lineage])

  // Compute selected-related node/edge sets
  const { highlightedNodeIds, highlightedEdgeIds, affectedRevisionIds } = useMemo(() => {
    if (!selectedNodeId) {
      return { highlightedNodeIds: null, highlightedEdgeIds: null, affectedRevisionIds: null }
    }

    // Find derivation edges coming into this generated node
    const derivEdges = allBaseEdges.filter(
      (e) =>
        e.data?.generated_node_id === selectedNodeId.replace('gen-', '') &&
        e.id.startsWith('e-deriv-'),
    )

    const sourceNodeIds = new Set(derivEdges.map((e) => e.source))
    const edgeIds = new Set(derivEdges.map((e) => e.id))

    // Find revisions whose payload references this node
    const genId = selectedNodeId.replace('gen-', '')
    const revIds = new Set<string>()
    for (const rev of lineage.revisions) {
      const p = rev.payload as Record<string, unknown>
      if (p.node_id === genId || p.anchor_id === genId) {
        revIds.add(`rev-${rev.id}`)
      }
    }

    return {
      highlightedNodeIds: new Set([selectedNodeId, ...sourceNodeIds, ...revIds]),
      highlightedEdgeIds: edgeIds,
      affectedRevisionIds: revIds,
    }
  }, [selectedNodeId, allBaseEdges, lineage.revisions])

  // Apply column visibility + selection highlighting to nodes
  const visibleNodes = useMemo(() => {
    return allBaseNodes
      .filter((node) => {
        const col = node.data.column
        if (col === 'source' && !showSources) return false
        if (col === 'generated' && !showGenerated) return false
        if (col === 'revision' && !showRevisions) return false
        return true
      })
      .map((node) => {
        if (!highlightedNodeIds) return node
        const isHighlighted = highlightedNodeIds.has(node.id)
        return {
          ...node,
          data: {
            ...node.data,
            isSelected: isHighlighted,
            isDimmed: !isHighlighted,
          },
        }
      })
  }, [allBaseNodes, showSources, showGenerated, showRevisions, highlightedNodeIds])

  // Apply visibility + selection to edges
  const visibleEdges = useMemo(() => {
    return allBaseEdges
      .filter((edge) => {
        // Hide edges whose source or target node is hidden
        const srcNode = allBaseNodes.find((n) => n.id === edge.source)
        const tgtNode = allBaseNodes.find((n) => n.id === edge.target)
        if (!srcNode || !tgtNode) return false
        if (srcNode.data.column === 'source' && !showSources) return false
        if (tgtNode.data.column === 'source' && !showSources) return false
        if (srcNode.data.column === 'generated' && !showGenerated) return false
        if (tgtNode.data.column === 'generated' && !showGenerated) return false
        if (srcNode.data.column === 'revision' && !showRevisions) return false
        if (tgtNode.data.column === 'revision' && !showRevisions) return false
        return true
      })
      .map((edge) => {
        if (!highlightedEdgeIds) return edge
        const isHighlighted = highlightedEdgeIds.has(edge.id)
        return {
          ...edge,
          style: {
            ...edge.style,
            opacity: isHighlighted ? 1 : 0.1,
          },
        }
      })
  }, [allBaseEdges, allBaseNodes, showSources, showGenerated, showRevisions, highlightedEdgeIds])

  const [nodes, setNodes, onNodesChange] = useNodesState(visibleNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(visibleEdges)

  // Sync external state changes into react-flow
  useEffect(() => {
    setNodes(visibleNodes)
  }, [visibleNodes, setNodes])

  useEffect(() => {
    setEdges(visibleEdges)
  }, [visibleEdges, setEdges])

  const handleNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      if (node.data.column === 'generated') {
        setSelectedNodeId((prev) => (prev === node.id ? null : node.id))
      }
    },
    [],
  )

  const handlePaneClick = useCallback(() => {
    setSelectedNodeId(null)
    setTooltip(null)
  }, [])

  const handleEdgeMouseEnter = useCallback(
    (event: React.MouseEvent, edge: Edge) => {
      if (edge.data?.text_excerpt) {
        setTooltip({
          x: event.clientX,
          y: event.clientY,
          text_excerpt: edge.data.text_excerpt as string,
          confidence: edge.data.confidence as number | undefined,
          page_numbers: edge.data.page_numbers as number[] | undefined,
        })
      }
    },
    [],
  )

  const handleEdgeMouseLeave = useCallback(() => {
    setTooltip(null)
  }, [])

  const handleToggle = useCallback((col: 'sources' | 'generated' | 'revisions') => {
    if (col === 'sources') setShowSources((v) => !v)
    if (col === 'generated') setShowGenerated((v) => !v)
    if (col === 'revisions') setShowRevisions((v) => !v)
  }, [])

  const handleReset = useCallback(() => {
    setSelectedNodeId(null)
    setTooltip(null)
  }, [])

  return (
    <div className="w-full h-full relative bg-[#0F1116]">
      <ColumnToolbar
        showSources={showSources}
        showGenerated={showGenerated}
        showRevisions={showRevisions}
        onToggle={handleToggle}
        onReset={handleReset}
        selectedNodeId={selectedNodeId}
      />

      {/* Column headers */}
      <div className="absolute top-3 left-0 right-0 z-10 pointer-events-none">
        <div className="flex justify-around px-8 pt-1">
          {showSources && (
            <span className="text-[10px] font-mono uppercase tracking-widest text-[#4B5563]">
              Sources
            </span>
          )}
          {showGenerated && (
            <span className="text-[10px] font-mono uppercase tracking-widest text-[#4B5563]">
              Generated Document
            </span>
          )}
          {showRevisions && (
            <span className="text-[10px] font-mono uppercase tracking-widest text-[#4B5563]">
              Revisions
            </span>
          )}
        </div>
      </div>

      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={handleNodeClick}
        onPaneClick={handlePaneClick}
        onEdgeMouseEnter={handleEdgeMouseEnter}
        onEdgeMouseLeave={handleEdgeMouseLeave}
        fitView
        fitViewOptions={{ padding: 0.15 }}
        minZoom={0.2}
        maxZoom={2}
        attributionPosition="bottom-right"
        proOptions={{ hideAttribution: true }}
      >
        <Background
          color="#1C2030"
          variant={BackgroundVariant.Dots}
          gap={24}
          size={1}
        />
        <Controls
          className="!bg-[#1C1F26] !border-[#374151] [&_button]:!bg-[#1C1F26] [&_button]:!border-[#374151] [&_button]:!text-[#9CA3AF] [&_button:hover]:!bg-[#2D3748]"
        />
        <MiniMap
          nodeColor={(node: Node<NodeBadgeData>) => {
            if (node.data?.column === 'source') return '#2D3748'
            if (node.data?.column === 'generated') return '#1C3A2E'
            return '#1C1F26'
          }}
          maskColor="rgba(15,17,22,0.6)"
          style={{ background: '#1C1F26', border: '1px solid #374151' }}
        />
      </ReactFlow>

      {/* Edge hover tooltip */}
      {tooltip && (
        <div
          className="fixed z-50 max-w-xs p-3 rounded-lg border border-[#374151] bg-[#1C1F26] shadow-xl text-xs pointer-events-none"
          style={{ left: tooltip.x + 12, top: tooltip.y - 8 }}
        >
          {tooltip.text_excerpt && (
            <p className="text-foreground italic mb-2">"{tooltip.text_excerpt}"</p>
          )}
          <div className="flex gap-3 text-muted-foreground">
            {tooltip.confidence !== undefined && (
              <span>
                Confidence:{' '}
                <span className="text-[#5EFCAB]">{(tooltip.confidence * 100).toFixed(0)}%</span>
              </span>
            )}
            {tooltip.page_numbers && tooltip.page_numbers.length > 0 && (
              <span>
                pp.{' '}
                <span className="text-foreground">{tooltip.page_numbers.join(', ')}</span>
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

// ─── Public wrapper — fetches data + provides ReactFlow context ───────────────
import { ReactFlowProvider } from 'reactflow'

interface LineageGraphProps {
  documentId: string
}

export function LineageGraph({ documentId }: LineageGraphProps) {
  const [lineage, setLineage] = useState<LineageResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    fetchLineage(documentId)
      .then((data) => {
        if (!cancelled) {
          setLineage(data)
          setLoading(false)
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Unknown error')
          setLoading(false)
        }
      })
    return () => {
      cancelled = true
    }
  }, [documentId])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full bg-[#0F1116]">
        <div className="flex items-center gap-3 text-muted-foreground">
          <div className="w-4 h-4 border-2 border-[#5EFCAB]/30 border-t-[#5EFCAB] rounded-full animate-spin" />
          <span className="text-sm font-mono">Loading lineage...</span>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full bg-[#0F1116]">
        <div className="text-center space-y-2">
          <p className="text-sm text-red-400">Failed to load lineage</p>
          <p className="text-xs text-muted-foreground font-mono">{error}</p>
        </div>
      </div>
    )
  }

  if (!lineage) return null

  return (
    <ReactFlowProvider>
      <GraphInner lineage={lineage} />
    </ReactFlowProvider>
  )
}
