'use client'

import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { MetricsPanel } from '@/components/MetricsPanel'
import { TaskQueuePanel } from '@/components/TaskQueuePanel'
import { HistoryPanel } from '@/components/HistoryPanel'
import { FileUploadDialog } from '@/components/FileUploadDialog'
import { useWebSocket } from '@/hooks/useWebSocket'
import { useToast } from '@/components/ui/toast'
import { PageHeader } from '@/components/ui/page-header'
import { StatusIndicator } from '@/components/ui/status-indicator'
import { Button } from '@/components/ui/button'
import { Plus } from 'lucide-react'

export default function Dashboard() {
  const { status, events } = useWebSocket()
  const queryClient = useQueryClient()
  const { addToast } = useToast()
  const [isUploadDialogOpen, setIsUploadDialogOpen] = useState(false)
  const [isUploading, setIsUploading] = useState(false)

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
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ documentId: document.id }),
      })

      if (!instanceResponse.ok) {
        throw new Error('Failed to create instance')
      }

      await instanceResponse.json()

      queryClient.invalidateQueries({ queryKey: ['documents'] })
      queryClient.invalidateQueries({ queryKey: ['instances'] })
      queryClient.invalidateQueries({ queryKey: ['metrics'] })

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
    <div className="max-w-7xl mx-auto">
      <PageHeader
        title="Overview"
        subtitle="System metrics and recent activity"
        breadcrumbs={[{ label: 'Dashboard' }, { label: 'Overview' }]}
        status={
          <StatusIndicator
            status={status === 'connected' ? 'active' : 'pending'}
            label={status === 'connected' ? 'Live' : 'Offline'}
          />
        }
        actions={
          <Button
            onClick={() => setIsUploadDialogOpen(true)}
            disabled={isUploading}
            className="gap-2"
          >
            <Plus className="w-4 h-4" />
            {isUploading ? 'Uploading...' : 'Open Instance'}
          </Button>
        }
      />

      <div className="space-y-6">
        <MetricsPanel />

        <TaskQueuePanel />

        <HistoryPanel recentEvents={events} />
      </div>

      <FileUploadDialog
        isOpen={isUploadDialogOpen}
        onClose={() => setIsUploadDialogOpen(false)}
        onFileSelect={handleFileSelect}
      />
    </div>
  )
}
