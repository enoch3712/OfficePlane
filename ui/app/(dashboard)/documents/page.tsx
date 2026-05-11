'use client'

import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { DocumentStructure } from '@/components/DocumentStructure'
import { DocumentsPanel } from '@/components/DocumentsPanel'
import { FileUploadDialog } from '@/components/FileUploadDialog'
import { useWebSocket } from '@/hooks/useWebSocket'
import { useToast } from '@/components/ui/toast'
import { PageHeader } from '@/components/ui/page-header'
import { StatusIndicator } from '@/components/ui/status-indicator'
import { Button } from '@/components/ui/button'
import { Plus } from 'lucide-react'
import { cn } from '@/lib/cn'

export default function DocumentsPage() {
  const { status } = useWebSocket()
  const queryClient = useQueryClient()
  const { addToast } = useToast()
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

      queryClient.invalidateQueries({ queryKey: ['documents'] })
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

  const tabs = [
    { key: 'overview' as const, label: 'Overview' },
    { key: 'planning' as const, label: 'Planning' },
  ]

  return (
    <div className="h-full flex flex-col -m-6 lg:-m-8">
      <div className="px-6 lg:px-8 pt-6 lg:pt-8">
        <PageHeader
          title="Documents"
          subtitle="Manage and plan document workflows"
          breadcrumbs={[{ label: 'Dashboard' }, { label: 'Documents' }]}
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
              {isUploading ? 'Uploading...' : 'Upload Document'}
            </Button>
          }
        />
      </div>

      <div className="flex-1 flex overflow-hidden">
        {/* Document tree sidebar */}
        <div className="w-80 flex-shrink-0 border-r border-border">
          <DocumentStructure />
        </div>

        {/* Main content */}
        <div className="flex-1 overflow-y-auto p-6 scrollbar-thin">
          <div className="max-w-6xl mx-auto space-y-6">
            {/* Tabs */}
            <div className="flex items-center gap-1 border-b border-border">
              {tabs.map((tab) => (
                <button
                  key={tab.key}
                  onClick={() => setActiveTab(tab.key)}
                  className={cn(
                    'px-4 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px',
                    activeTab === tab.key
                      ? 'border-b-primary text-primary'
                      : 'border-b-transparent text-muted-foreground hover:text-foreground'
                  )}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {activeTab === 'overview' && <DocumentsPanel />}
            {activeTab === 'planning' && (
              <div className="rounded-lg border border-dashed border-border bg-depth-1 p-6 text-sm text-muted-foreground">
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
