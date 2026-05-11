'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { Document } from '@/lib/types'
import {
  FileText,
  ChevronDown,
  ChevronRight,
  BookOpen,
  FileType,
  Hash,
  Search,
  Loader2,
  Trash2,
} from 'lucide-react'
import { ConfirmDialog } from './ConfirmDialog'

interface DocumentStructureProps {
  onSelectSection?: (documentId: string, chapterId?: string, sectionId?: string) => void
}

export function DocumentStructure({ onSelectSection }: DocumentStructureProps) {
  const queryClient = useQueryClient()
  const [selectedDoc, setSelectedDoc] = useState<string | null>(null)
  const [expandedChapters, setExpandedChapters] = useState<Set<string>>(new Set())
  const [searchTerm, setSearchTerm] = useState('')
  const [deleteTarget, setDeleteTarget] = useState<{ id: string; title: string } | null>(null)

  const { data: documents, isLoading } = useQuery({
    queryKey: ['documents'],
    queryFn: () => api.getDocuments(),
  })

  const { data: selectedDocument, isLoading: isLoadingDocument } = useQuery({
    queryKey: ['document-details', selectedDoc],
    queryFn: () => api.getDocument(selectedDoc!),
    enabled: !!selectedDoc,
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteDocument(id),
    onSuccess: (_, deletedId) => {
      // Clear selection if the deleted document was selected
      if (selectedDoc === deletedId) {
        setSelectedDoc(null)
        setExpandedChapters(new Set())
      }
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

  const toggleChapter = (chapterId: string) => {
    const newExpanded = new Set(expandedChapters)
    if (newExpanded.has(chapterId)) {
      newExpanded.delete(chapterId)
    } else {
      newExpanded.add(chapterId)
    }
    setExpandedChapters(newExpanded)
  }

  const handleSelectDocument = (docId: string) => {
    if (selectedDoc === docId) {
      setSelectedDoc(null)
      setExpandedChapters(new Set())
    } else {
      setSelectedDoc(docId)
      setExpandedChapters(new Set())
    }
    onSelectSection?.(docId)
  }

  const handleSelectSection = (chapterId: string, sectionId: string) => {
    if (selectedDoc) {
      onSelectSection?.(selectedDoc, chapterId, sectionId)
    }
  }

  if (isLoading) {
    return (
      <div className="h-full bg-[#060a14] border-r border-white/10">
        <div className="p-4 border-b border-white/10">
          <div className="h-6 bg-white/10 rounded animate-pulse" />
        </div>
        <div className="p-4 space-y-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-12 bg-white/5 rounded animate-pulse" />
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="h-full bg-[#060a14] border-r border-white/10 flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-white/10">
        <h2 className="text-lg font-semibold text-white mb-3">Documents</h2>
        <div className="relative">
          <Search className="absolute left-3 top-2.5 w-4 h-4 text-slate-500" />
          <input
            type="text"
            placeholder="Search documents..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-3 py-2 text-sm border border-white/10 bg-white/[0.03] text-white rounded-lg focus:outline-none focus:ring-2 focus:ring-[#39ff14]/30 focus:border-transparent"
          />
        </div>
      </div>

      {/* Document List */}
      <div className="flex-1 overflow-y-auto">
        {!documents || documents.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-slate-500 p-8">
            <FileText className="w-16 h-16 mb-3" />
            <p className="text-sm text-center">No documents uploaded</p>
          </div>
        ) : (
          <div className="p-2">
            {documents
              .filter((doc) =>
                doc.title.toLowerCase().includes(searchTerm.toLowerCase())
              )
              .map((document) => {
                const isSelected = selectedDoc === document.id
                const fullDoc = isSelected ? selectedDocument : null

                return (
                  <div key={document.id} className="mb-2 group">
                    {/* Document Header */}
                    <div
                      className={`w-full flex items-center gap-2 px-3 py-2.5 rounded-lg transition-colors ${
                        isSelected
                          ? 'bg-[#39ff14]/10 text-[#39ff14]'
                          : 'hover:bg-white/[0.03] text-slate-200'
                      }`}
                    >
                      <button
                        onClick={() => handleSelectDocument(document.id)}
                        className="flex-1 flex items-center gap-2 text-left"
                      >
                        <ChevronRight
                          className={`w-4 h-4 transition-transform ${
                            isSelected ? 'rotate-90' : ''
                          }`}
                        />
                        <FileText className="w-4 h-4" />
                        <span className="flex-1 text-sm font-medium truncate">
                          {document.title}
                        </span>
                        <span className="text-xs text-slate-500">
                          {document.total_chapters || 0}
                        </span>
                      </button>
                      <button
                        onClick={(e) => handleDeleteClick(e, document.id, document.title)}
                        className="p-1.5 opacity-0 group-hover:opacity-100 text-slate-500 hover:text-red-400 hover:bg-red-500/10 rounded transition-all"
                        title="Delete document"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>

                    {/* Loading Indicator */}
                    {isSelected && isLoadingDocument && (
                      <div className="mt-1 ml-6 flex items-center gap-2 px-3 py-4 text-slate-500">
                        <Loader2 className="w-4 h-4 animate-spin" />
                        <span className="text-sm">Loading document structure...</span>
                      </div>
                    )}

                    {/* Chapters and Sections */}
                    {isSelected && fullDoc?.chapters && !isLoadingDocument && (
                      <div className="mt-1 ml-6 space-y-1">
                        {fullDoc.chapters.map((chapter) => {
                          const isChapterExpanded = expandedChapters.has(chapter.id)

                          return (
                            <div key={chapter.id}>
                              {/* Chapter */}
                              <button
                                onClick={() => toggleChapter(chapter.id)}
                                className="w-full flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-white/[0.03] text-slate-200 transition-colors"
                              >
                                <ChevronRight
                                  className={`w-3.5 h-3.5 transition-transform ${
                                    isChapterExpanded ? 'rotate-90' : ''
                                  }`}
                                />
                                <BookOpen className="w-3.5 h-3.5 text-blue-400" />
                                <span className="flex-1 text-left text-sm truncate">
                                  {chapter.order_index + 1}. {chapter.title}
                                </span>
                                <span className="text-xs text-slate-500">
                                  {chapter.sections.length}
                                </span>
                              </button>

                              {/* Sections */}
                              {isChapterExpanded && chapter.sections.length > 0 && (
                                <div className="ml-6 mt-1 space-y-0.5">
                                  {chapter.sections.map((section) => (
                                    <button
                                      key={section.id}
                                      onClick={() =>
                                        handleSelectSection(chapter.id, section.id)
                                      }
                                      className="w-full flex items-center gap-2 px-3 py-1.5 rounded-lg hover:bg-blue-500/10 text-slate-400 hover:text-blue-400 transition-colors"
                                    >
                                      <FileType className="w-3 h-3" />
                                      <span className="flex-1 text-left text-xs truncate">
                                        {chapter.order_index + 1}.{section.order_index + 1}{' '}
                                        {section.title}
                                      </span>
                                      <div className="flex items-center gap-1 text-xs text-slate-500">
                                        <Hash className="w-3 h-3" />
                                        {section.page_count}
                                      </div>
                                    </button>
                                  ))}
                                </div>
                              )}
                            </div>
                          )
                        })}
                      </div>
                    )}
                  </div>
                )
              })}
          </div>
        )}
      </div>

      {/* Footer Stats */}
      {documents && documents.length > 0 && (
        <div className="p-4 border-t border-white/10 bg-white/[0.03]">
          <div className="text-xs text-slate-400">
            <div className="flex justify-between mb-1">
              <span>Total Documents:</span>
              <span className="font-medium text-white">{documents.length}</span>
            </div>
            <div className="flex justify-between">
              <span>Total Chapters:</span>
              <span className="font-medium text-white">
                {documents.reduce((sum, doc) => sum + (doc.total_chapters || 0), 0)}
              </span>
            </div>
          </div>
        </div>
      )}

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
