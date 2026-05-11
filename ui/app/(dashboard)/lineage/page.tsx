'use client'

import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import Link from 'next/link'
import { GitBranch, FileText, ArrowRight } from 'lucide-react'
import { PageHeader } from '@/components/ui/page-header'
import { cn } from '@/lib/cn'

export default function LineageIndexPage() {
  const { data: documents, isLoading } = useQuery({
    queryKey: ['documents'],
    queryFn: () => api.getDocuments(),
  })

  return (
    <div className="max-w-3xl mx-auto">
      <PageHeader
        title="Source Trail"
        subtitle="Select a document to view its lineage map"
        breadcrumbs={[{ label: 'Dashboard' }, { label: 'Source Trail' }]}
      />

      {isLoading && (
        <div className="flex items-center gap-3 text-muted-foreground py-8">
          <div className="w-4 h-4 border-2 border-[#5EFCAB]/30 border-t-[#5EFCAB] rounded-full animate-spin" />
          <span className="text-sm font-mono">Loading documents...</span>
        </div>
      )}

      {!isLoading && (!documents || documents.length === 0) && (
        <div className="rounded-lg border border-dashed border-border bg-depth-1 p-10 text-center">
          <FileText className="w-10 h-10 text-muted-foreground/40 mx-auto mb-3" />
          <p className="text-sm text-muted-foreground">No documents available.</p>
          <p className="text-xs text-muted-foreground/60 mt-1">
            Upload a document first, then view its source trail here.
          </p>
        </div>
      )}

      {documents && documents.length > 0 && (
        <div className="space-y-2">
          {documents.map((doc) => (
            <Link
              key={doc.id}
              href={`/lineage/${doc.id}`}
              className={cn(
                'flex items-center gap-4 p-4 rounded-lg border border-border bg-depth-1',
                'hover:border-[#5EFCAB]/40 hover:bg-[#5EFCAB]/5 transition-all group',
              )}
            >
              <div className="w-8 h-8 rounded bg-[#5EFCAB]/10 border border-[#5EFCAB]/20 flex items-center justify-center shrink-0">
                <GitBranch className="w-4 h-4 text-[#5EFCAB]" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-foreground truncate">{doc.title}</p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {doc.total_chapters} chapters · {doc.total_sections} sections
                </p>
              </div>
              <ArrowRight className="w-4 h-4 text-muted-foreground group-hover:text-[#5EFCAB] transition-colors shrink-0" />
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
