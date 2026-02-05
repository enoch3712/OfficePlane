'use client'

import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { MetricsPanel } from '@/components/MetricsPanel'
import { InstancesPanel } from '@/components/InstancesPanel'
import { TaskQueuePanel } from '@/components/TaskQueuePanel'
import { HistoryPanel } from '@/components/HistoryPanel'
import { FileUploadDialog } from '@/components/FileUploadDialog'
import { useWebSocket } from '@/hooks/useWebSocket'
import { useToast } from '@/components/ui/toast'
import { Bell, HelpCircle, Plus } from 'lucide-react'

export default function Dashboard() {
  const { status, events } = useWebSocket()
  const queryClient = useQueryClient()
  const { addToast } = useToast()
  const [isUploadDialogOpen, setIsUploadDialogOpen] = useState(false)
  const [isUploading, setIsUploading] = useState(false)

  const handleFileSelect = async (file: File) => {
    setIsUploading(true)
    try {
      // Create FormData for file upload
      const formData = new FormData()
      formData.append('file', file)

      // Upload to API
      const response = await fetch('http://localhost:8001/api/documents/upload', {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || 'Upload failed')
      }

      const document = await response.json()
      console.log('Document uploaded successfully:', document)

      // Create an instance with the uploaded document
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

      const instance = await instanceResponse.json()
      console.log('Instance created successfully:', instance)

      // Refresh queries
      queryClient.invalidateQueries({ queryKey: ['documents'] })
      queryClient.invalidateQueries({ queryKey: ['instances'] })
      queryClient.invalidateQueries({ queryKey: ['metrics'] })

      // Show success toast
      addToast({
        type: 'document',
        title: 'Document uploaded successfully',
        description: `"${document.title}" is ready`,
        details: [
          { label: 'Chapters', value: document.total_chapters },
          { label: 'Pages', value: document.total_pages },
        ],
        duration: 6000,
      })
    } catch (error) {
      console.error('Upload error:', error)
      addToast({
        type: 'error',
        title: 'Upload failed',
        description: error instanceof Error ? error.message : 'Unknown error',
        duration: 8000,
      })
    } finally {
      setIsUploading(false)
    }
  }

  return (
    <div className="min-h-full flex flex-col bg-gray-50">
      {/* Top Bar */}
      <header className="h-16 bg-white border-b border-gray-200 flex items-center justify-between px-6">
        <div className="flex items-center gap-4">
          <h1 className="text-xl font-semibold text-gray-900">Overview</h1>
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

      {/* Main Content */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-7xl mx-auto space-y-6">
          {/* Welcome Section */}
          <div className="bg-gradient-to-r from-orange-500 to-orange-600 rounded-xl p-6 text-white">
            <h2 className="text-2xl font-bold mb-2">Welcome to OfficePlane</h2>
            <p className="text-orange-100">
              Agentic framework for Office document manipulation at scale
            </p>
          </div>

          {/* Metrics Overview */}
          <MetricsPanel />

          {/* Two Column Layout */}
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
            <InstancesPanel />
            <TaskQueuePanel />
          </div>

          {/* Activity History */}
          <HistoryPanel recentEvents={events} />
        </div>
      </div>

      {/* File Upload Dialog */}
      <FileUploadDialog
        isOpen={isUploadDialogOpen}
        onClose={() => setIsUploadDialogOpen(false)}
        onFileSelect={handleFileSelect}
      />
    </div>
  )
}
