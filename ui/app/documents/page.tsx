'use client'

import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { DocumentStructure } from '@/components/DocumentStructure'
import { DocumentsPanel } from '@/components/DocumentsPanel'
import { FileUploadDialog } from '@/components/FileUploadDialog'
import { useWebSocket } from '@/hooks/useWebSocket'
import { Bell, HelpCircle, Plus } from 'lucide-react'

export default function DocumentsPage() {
  const { status } = useWebSocket()
  const queryClient = useQueryClient()
  const [isUploadDialogOpen, setIsUploadDialogOpen] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [activeTab, setActiveTab] = useState<'overview' | 'planning'>('overview')

  const handleFileSelect = async (file: File) => {
    setIsUploading(true)
    try {
      const formData = new FormData()
      formData.append('file', file)

      const response = await fetch('http://localhost:8001/api/documents/upload', {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || 'Upload failed')
      }

      const document = await response.json()

      const instanceResponse = await fetch('http://localhost:8001/api/instances', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          documentId: document.id,
        }),
      })

      if (!instanceResponse.ok) {
        throw new Error('Failed to create instance')
      }

      await instanceResponse.json()

      queryClient.invalidateQueries({ queryKey: ['documents'] })
      queryClient.invalidateQueries({ queryKey: ['instances'] })
      queryClient.invalidateQueries({ queryKey: ['metrics'] })

      alert(
        `Document "${document.title}" uploaded and instance created!\n\nChapters: ${document.total_chapters}\nPages: ${document.total_pages}`
      )
    } catch (error) {
      alert(`Failed: ${error instanceof Error ? error.message : 'Unknown error'}`)
    } finally {
      setIsUploading(false)
    }
  }

  return (
    <div className="h-screen flex flex-col bg-gray-50">
      <header className="h-16 bg-white border-b border-gray-200 flex items-center justify-between px-6">
        <div className="flex items-center gap-4">
          <h1 className="text-xl font-semibold text-gray-900">Documents</h1>
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
          <button
            onClick={() => setIsUploadDialogOpen(true)}
            disabled={isUploading}
            className="flex items-center gap-2 px-4 py-2 bg-orange-500 text-white rounded-lg hover:bg-orange-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-orange-500/20"
          >
            <Plus className="w-4 h-4" />
            <span className="text-sm font-medium">
              {isUploading ? 'Uploading...' : 'Open Instance'}
            </span>
          </button>
        </div>
      </header>

      <div className="flex-1 flex overflow-hidden">
        <div className="w-80 flex-shrink-0">
          <DocumentStructure />
        </div>

        <div className="flex-1 overflow-y-auto p-6">
          <div className="max-w-6xl mx-auto space-y-6">
            <div className="flex items-center gap-2 border-b border-gray-200">
              <button
                onClick={() => setActiveTab('overview')}
                className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === 'overview'
                    ? 'border-orange-500 text-orange-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700'
                }`}
              >
                Overview
              </button>
              <button
                onClick={() => setActiveTab('planning')}
                className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === 'planning'
                    ? 'border-orange-500 text-orange-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700'
                }`}
              >
                Planning
              </button>
            </div>

            {activeTab === 'overview' && <DocumentsPanel />}
            {activeTab === 'planning' && (
              <div className="rounded-xl border border-dashed border-gray-200 bg-white p-6 text-sm text-gray-500">
                Use the Agentic Chat panel in the left sidebar to generate plans and
                manipulate documents.
              </div>
            )}
          </div>
        </div>
      </div>

      <FileUploadDialog
        isOpen={isUploadDialogOpen}
        onClose={() => setIsUploadDialogOpen(false)}
        onFileSelect={handleFileSelect}
      />
    </div>
  )
}
