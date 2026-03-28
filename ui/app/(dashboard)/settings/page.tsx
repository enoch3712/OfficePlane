'use client'

import { useState, useRef, useEffect } from 'react'
import { Database, Brain, Search, MessageSquare, ExternalLink, ChevronDown } from 'lucide-react'
import { PageHeader } from '@/components/ui/page-header'
import { Card } from '@/components/ui/card'

interface ComponentOption {
  id: string
  name: string
  url?: string
}

interface ConfigCategory {
  id: string
  label: string
  description: string
  icon: React.ReactNode
  options: ComponentOption[]
}

const categories: ConfigCategory[] = [
  {
    id: 'memory',
    label: 'Agent Memory',
    description: 'Cross-session context and learned patterns',
    icon: <Brain className="h-4 w-4" />,
    options: [
      { id: '', name: 'Not configured' },
      { id: 'mem0', name: 'Mem0', url: 'https://mem0.ai' },
      { id: 'zep', name: 'Zep', url: 'https://getzep.com' },
      { id: 'redis', name: 'Redis', url: 'https://redis.io' },
      { id: 'letta', name: 'Letta', url: 'https://letta.com' },
    ],
  },
  {
    id: 'vector_store',
    label: 'Vector Store (RAG)',
    description: 'Document embeddings for semantic retrieval',
    icon: <Search className="h-4 w-4" />,
    options: [
      { id: 'pgvector', name: 'pgvector', url: 'https://github.com/pgvector/pgvector' },
      { id: 'pinecone', name: 'Pinecone', url: 'https://pinecone.io' },
      { id: 'weaviate', name: 'Weaviate', url: 'https://weaviate.io' },
      { id: 'qdrant', name: 'Qdrant', url: 'https://qdrant.tech' },
    ],
  },
  {
    id: 'llm',
    label: 'LLM Provider',
    description: 'Model provider for reasoning and generation',
    icon: <MessageSquare className="h-4 w-4" />,
    options: [
      { id: 'anthropic', name: 'Anthropic (Claude)', url: 'https://anthropic.com' },
      { id: 'google', name: 'Google (Gemini)', url: 'https://ai.google.dev' },
      { id: 'openai', name: 'OpenAI', url: 'https://openai.com' },
      { id: 'ollama', name: 'Ollama', url: 'https://ollama.com' },
    ],
  },
  {
    id: 'broker',
    label: 'Message Broker',
    description: 'Task dispatch and inter-agent communication',
    icon: <Database className="h-4 w-4" />,
    options: [
      { id: 'memory', name: 'In-Memory' },
      { id: 'redis', name: 'Redis', url: 'https://redis.io' },
    ],
  },
]

const defaults: Record<string, string> = {
  memory: '',
  vector_store: 'pgvector',
  llm: 'google',
  broker: 'memory',
}

function Select({
  value,
  options,
  onChange,
}: {
  value: string
  options: ComponentOption[]
  onChange: (id: string) => void
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  const selected = options.find((o) => o.id === value)

  return (
    <div ref={ref} className="relative flex-1">
      <button
        onClick={() => setOpen(!open)}
        className={`w-full flex items-center justify-between rounded-md border bg-depth-2 px-3 py-1.5 text-sm font-mono transition-colors cursor-pointer ${
          open
            ? 'border-primary/50 ring-1 ring-primary/25'
            : 'border-border hover:border-muted-foreground/40'
        }`}
      >
        <span className={selected?.id ? 'text-foreground' : 'text-muted-foreground'}>
          {selected?.name ?? 'Select...'}
        </span>
        <ChevronDown className={`h-3.5 w-3.5 text-muted-foreground transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div className="absolute z-50 mt-1 w-full rounded-md border border-border bg-depth-3 py-1 shadow-lg shadow-black/40">
          {options.map((option) => (
            <button
              key={option.id}
              onClick={() => { onChange(option.id); setOpen(false) }}
              className={`w-full text-left px-3 py-1.5 text-sm font-mono transition-colors ${
                option.id === value
                  ? 'text-primary bg-primary/10'
                  : 'text-foreground hover:bg-depth-2'
              }`}
            >
              {option.name}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

export default function SettingsPage() {
  const [selections, setSelections] = useState<Record<string, string>>(defaults)

  const getSelectedUrl = (category: ConfigCategory) => {
    const selected = category.options.find((o) => o.id === selections[category.id])
    return selected?.url
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <PageHeader
        title="Settings"
        subtitle="Configure pluggable components for the agent platform"
        breadcrumbs={[{ label: 'Dashboard' }, { label: 'Settings' }]}
      />

      <Card accent title="Platform Components" subtitle="Select providers for each layer of the agent stack.">
        <div className="space-y-4">
          {categories.map((category) => (
            <div key={category.id} className="flex items-center gap-4">
              <div className="flex items-center gap-2.5 w-48 shrink-0">
                <span className="text-muted-foreground">{category.icon}</span>
                <div>
                  <div className="text-sm font-heading font-semibold text-foreground leading-tight">
                    {category.label}
                  </div>
                  <div className="text-[10px] text-muted-foreground">{category.description}</div>
                </div>
              </div>

              <Select
                value={selections[category.id]}
                options={category.options}
                onChange={(id) => setSelections((prev) => ({ ...prev, [category.id]: id }))}
              />

              {getSelectedUrl(category) ? (
                <a
                  href={getSelectedUrl(category)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-muted-foreground hover:text-primary transition-colors shrink-0"
                >
                  <ExternalLink className="h-3.5 w-3.5" />
                </a>
              ) : (
                <div className="w-3.5 shrink-0" />
              )}
            </div>
          ))}
        </div>
      </Card>
    </div>
  )
}
