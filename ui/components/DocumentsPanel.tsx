'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { Document } from '@/lib/types'
import { FileText, ChevronDown, ChevronRight, BookOpen, FileType, Hash, Trash2, GitBranch } from 'lucide-react'
import { TimeAgo } from './TimeAgo'
import { ConfirmDialog } from './ConfirmDialog'
import { StatusBadge } from './documents/StatusBadge'
import { DocumentStatus } from '@/lib/api/lifecycle'

export function DocumentsPanel() {
  const queryClient = useQueryClient()
  const [expandedDocs, setExpandedDocs] = useState<Set<string>>(new Set())
  const [expandedChapters, setExpandedChapters] = useState<Set<string>>(new Set())
  const [deleteTarget, setDeleteTarget] = useState<{ id: string; title: string } | null>(null)

  const { data: documents, isLoading } = useQuery({
    queryKey: ['documents'],
    queryFn: () => api.getDocuments(),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteDocument(id),
    onSuccess: (_, deletedId) => {
      // Remove from expanded if it was expanded
      setExpandedDocs((prev) => {
        const newSet = new Set(prev)
        newSet.delete(deletedId)
        return newSet
      })
      // Refresh queries
      queryClient.invalidateQueries({ queryKey: ['documents'] })
      queryClient.invalidateQueries({ queryKey: ['metrics'] })
      setDeleteTarget(null)
    },
    onError: (error) => {
      alert(`Failed to delete document: ${error instanceof Error ? error.message : 'Unknown error'}`)
    },
  })

  const handleDeleteClick = (e: React.MouseEvent, docId: string, docTitle: string) => {
    e.stopPropagation()
    setDeleteTarget({ id: docId, title: docTitle })
  }

  const handleConfirmDelete = () => {
    if (deleteTarget) {
      deleteMutation.mutate(deleteTarget.id)
    }
  }

  const { data: expandedDocDetails, refetch: refetchDetails } = useQuery({
    queryKey: ['document-details', Array.from(expandedDocs)],
    queryFn: async () => {
      const details = await Promise.all(
        Array.from(expandedDocs).map((id) => api.getDocument(id))
      )
      return details.reduce((acc, doc) => {
        acc[doc.id] = doc
        return acc
      }, {} as Record<string, Document>)
    },
    enabled: expandedDocs.size > 0,
  })

  const toggleDocument = (docId: string) => {
    const newExpanded = new Set(expandedDocs)
    if (newExpanded.has(docId)) {
      newExpanded.delete(docId)
    } else {
      newExpanded.add(docId)
    }
    setExpandedDocs(newExpanded)
  }

  const toggleChapter = (chapterId: string) => {
    const newExpanded = new Set(expandedChapters)
    if (newExpanded.has(chapterId)) {
      newExpanded.delete(chapterId)
    } else {
      newExpanded.add(chapterId)
    }
    setExpandedChapters(newExpanded)
  }

  if (isLoading) {
    return (
      <div className="bg-white/[0.02] rounded-lg shadow p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-6 bg-white/10 rounded w-48" />
          <div className="space-y-3">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="h-20 bg-white/5 rounded" />
            ))}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-white/[0.02] rounded-lg shadow flex flex-col h-[600px]">
      <div className="p-6 border-b border-white/10">
        <div>
          <h2 className="text-lg font-semibold text-white">Documents</h2>
          <p className="text-sm text-slate-500">{documents?.length || 0} documents</p>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        {!documents || documents.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-slate-500">
            <FileText className="w-16 h-16 mb-4" />
            <p className="text-sm">No documents uploaded</p>
          </div>
        ) : (
          <div className="space-y-3">
            {documents.map((document) => {
              const isExpanded = expandedDocs.has(document.id)
              const fullDoc = expandedDocDetails?.[document.id]

              return (
                <div
                  key={document.id}
                  className="group border border-white/10 rounded-lg hover:border-[#39ff14]/30 hover:shadow-sm transition-all"
                >
                  {/* Document Header */}
                  <div
                    className="p-4 cursor-pointer"
                    onClick={() => toggleDocument(document.id)}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-2">
                          <button
                            className="p-1 hover:bg-white/5 rounded transition-colors"
                            onClick={(e) => {
                              e.stopPropagation()
                              toggleDocument(document.id)
                            }}
                          >
                            {isExpanded ? (
                              <ChevronDown className="w-4 h-4 text-slate-400" />
                            ) : (
                              <ChevronRight className="w-4 h-4 text-slate-400" />
                            )}
                          </button>
                          <FileText className="w-4 h-4 text-[#39ff14]" />
                          <span className="font-medium text-white">
                            {document.title}
                          </span>
                          <StatusBadge status={(document.status as DocumentStatus) ?? 'DRAFT'} />
                        </div>

                        <div className="ml-7 grid grid-cols-3 gap-x-4 gap-y-1 text-sm">
                          {document.author && (
                            <div className="text-slate-500">
                              Author: <span className="text-white">{document.author}</span>
                            </div>
                          )}
                          <div className="text-slate-500">
                            Chapters:{' '}
                            <span className="text-white">{document.total_chapters || 0}</span>
                          </div>
                          <div className="text-slate-500">
                            Sections:{' '}
                            <span className="text-white">{document.total_sections || 0}</span>
                          </div>
                          {document.createdAt && (
                            <div className="text-slate-500 text-xs col-span-3">
                              Uploaded <TimeAgo date={document.createdAt} />
                            </div>
                          )}
                        </div>
                      </div>

                      {/* Actions */}
                      <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-all">
                        <Link
                          href={`/lineage/${document.id}`}
                          onClick={(e) => e.stopPropagation()}
                          className="p-2 text-slate-500 hover:text-[#5EFCAB] hover:bg-[#5EFCAB]/10 rounded-lg transition-all"
                          title="View source trail"
                        >
                          <GitBranch className="w-4 h-4" />
                        </Link>
                        <button
                          onClick={(e) => handleDeleteClick(e, document.id, document.title)}
                          className="p-2 text-slate-500 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-all"
                          title="Delete document"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  </div>

                  {/* Expanded Document Structure */}
                  {isExpanded && fullDoc?.chapters && (
                    <div className="border-t border-white/10 bg-white/[0.03] p-4">
                      <div className="space-y-2">
                        {fullDoc.chapters.map((chapter) => {
                          const isChapterExpanded = expandedChapters.has(chapter.id)

                          return (
                            <div
                              key={chapter.id}
                              className="bg-white/[0.02] rounded border border-white/10"
                            >
                              {/* Chapter Header */}
                              <div
                                className="p-3 cursor-pointer hover:bg-white/[0.03] transition-colors"
                                onClick={() => toggleChapter(chapter.id)}
                              >
                                <div className="flex items-center gap-2">
                                  <button
                                    className="p-1 hover:bg-white/5 rounded transition-colors"
                                    onClick={(e) => {
                                      e.stopPropagation()
                                      toggleChapter(chapter.id)
                                    }}
                                  >
                                    {isChapterExpanded ? (
                                      <ChevronDown className="w-3 h-3 text-slate-400" />
                                    ) : (
                                      <ChevronRight className="w-3 h-3 text-slate-400" />
                                    )}
                                  </button>
                                  <BookOpen className="w-3 h-3 text-[#39ff14]" />
                                  <span className="text-sm font-medium text-white">
                                    {chapter.order_index + 1}. {chapter.title}
                                  </span>
                                  <span className="text-xs text-slate-500">
                                    ({chapter.sections.length} sections)
                                  </span>
                                </div>
                              </div>

                              {/* Sections */}
                              {isChapterExpanded && chapter.sections.length > 0 && (
                                <div className="border-t border-white/10 bg-white/[0.03] p-3 space-y-1">
                                  {chapter.sections.map((section) => (
                                    <div
                                      key={section.id}
                                      className="flex items-center gap-2 text-xs text-slate-200 py-1 px-2 hover:bg-white/[0.02] rounded transition-colors"
                                    >
                                      <FileType className="w-3 h-3 text-slate-500" />
                                      <span>
                                        {chapter.order_index + 1}.{section.order_index + 1}{' '}
                                        {section.title}
                                      </span>
                                      <span className="ml-auto flex items-center gap-1 text-slate-500">
                                        <Hash className="w-3 h-3" />
                                        {section.page_count} pages
                                      </span>
                                    </div>
                                  ))}
                                </div>
                              )}
                            </div>
                          )
                        })}
                      </div>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Delete Confirmation Dialog */}
      <ConfirmDialog
        isOpen={deleteTarget !== null}
        onClose={() => setDeleteTarget(null)}
        onConfirm={handleConfirmDelete}
        title="Delete Document"
        message={`Are you sure you want to delete "${deleteTarget?.title}"? This action cannot be undone.`}
        confirmText="Delete"
        cancelText="Cancel"
        variant="danger"
        isLoading={deleteMutation.isPending}
      />
    </div>
  )
}
