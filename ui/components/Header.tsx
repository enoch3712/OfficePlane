'use client'

import { useState } from 'react'
import { FileText, Activity, Plus, Sparkles } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { FileUploadDialog } from '@/components/FileUploadDialog'
import { useToast } from '@/components/ui/toast'

interface HeaderProps {
  connectionStatus: 'connecting' | 'connected' | 'disconnected' | 'error'
}

export function Header({ connectionStatus }: HeaderProps) {
  const [isUploadDialogOpen, setIsUploadDialogOpen] = useState(false)
  const { addToast } = useToast()

  const statusColors = {
    connecting: 'bg-warning',
    connected: 'bg-success',
    disconnected: 'bg-muted-foreground',
    error: 'bg-destructive',
  }

  const statusText = {
    connecting: 'Connecting',
    connected: 'Live',
    disconnected: 'Disconnected',
    error: 'Error',
  }

  const handleFileSelect = async (file: File) => {
    console.log('File selected:', file.name)

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
    }
  }

  return (
    <>
      <header className="bg-card/95 border-b border-border sticky top-0 z-40 shadow-sm">
        <div className="max-w-[1800px] mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            {/* Logo */}
            <div className="flex items-center gap-3">
              <div className="relative">
                <div className="absolute inset-0 bg-gradient-to-br from-primary to-accent blur-xl opacity-20 rounded-full" />
                <div className="relative bg-gradient-to-br from-primary to-accent p-2 rounded-xl">
                  <FileText className="w-6 h-6 text-primary-foreground" />
                </div>
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h1 className="text-2xl font-bold bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent">
                    OfficePlane
                  </h1>
                  <Sparkles className="w-4 h-4 text-accent" />
                </div>
                <p className="text-sm text-muted-foreground">Agentic Document Management</p>
              </div>
            </div>

            {/* Actions */}
            <div className="flex items-center gap-3">
              {/* Connection Status */}
              <div className="flex items-center gap-2 px-3 py-2 bg-secondary/50 rounded-lg border border-border">
                <div className="relative">
                  <Activity className="w-4 h-4 text-foreground" />
                  <div
                    className={`absolute -top-1 -right-1 w-2.5 h-2.5 ${statusColors[connectionStatus]} rounded-full ${
                      connectionStatus === 'connected' ? 'animate-pulse' : ''
                    }`}
                  />
                </div>
                <span className="text-sm font-medium text-foreground">
                  {statusText[connectionStatus]}
                </span>
              </div>

              {/* Upload Document Button */}
              <Button
                onClick={() => setIsUploadDialogOpen(true)}
                className="gap-2 shadow-lg shadow-primary/20 hover:shadow-xl hover:shadow-primary/30 transition-all duration-200"
              >
                <Plus className="w-4 h-4" />
                Upload Document
              </Button>
            </div>
          </div>
        </div>
      </header>

      {/* File Upload Dialog */}
      <FileUploadDialog
        isOpen={isUploadDialogOpen}
        onClose={() => setIsUploadDialogOpen(false)}
        onFileSelect={handleFileSelect}
      />
    </>
  )
}
