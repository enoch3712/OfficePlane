'use client'

import { useState, useRef } from 'react'
import { Upload, FileText, X, Check } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/cn'

interface FileUploadDialogProps {
  isOpen: boolean
  onClose: () => void
  onFileSelect: (file: File) => void
}

export function FileUploadDialog({ isOpen, onClose, onFileSelect }: FileUploadDialogProps) {
  const [dragActive, setDragActive] = useState(false)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true)
    } else if (e.type === "dragleave") {
      setDragActive(false)
    }
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFile(e.dataTransfer.files[0])
    }
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    e.preventDefault()
    if (e.target.files && e.target.files[0]) {
      handleFile(e.target.files[0])
    }
  }

  const handleFile = (file: File) => {
    const allowedTypes = [
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document', // .docx
      'application/msword', // .doc
    ]

    if (allowedTypes.includes(file.type) || file.name.endsWith('.doc') || file.name.endsWith('.docx')) {
      setSelectedFile(file)
    } else {
      alert('Please select a Word document (.doc or .docx)')
    }
  }

  const handleSubmit = () => {
    if (selectedFile) {
      onFileSelect(selectedFile)
      setSelectedFile(null)
      onClose()
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-background/80 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Dialog */}
      <div className="relative w-full max-w-lg mx-4 bg-card border border-border rounded-lg shadow-2xl animate-in fade-in-0 zoom-in-95 duration-200">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-border">
          <div>
            <h2 className="text-2xl font-semibold text-foreground">Open Instance</h2>
            <p className="text-sm text-muted-foreground mt-1">Upload a Word document to get started</p>
          </div>
          <button
            onClick={onClose}
            className="rounded-full p-2 hover:bg-accent transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6">
          {/* Drag and Drop Area */}
          <div
            className={cn(
              "relative border-2 border-dashed rounded-lg p-12 transition-all duration-200",
              dragActive
                ? "border-primary bg-primary/5 scale-105"
                : "border-border hover:border-primary/50 hover:bg-accent/5",
              selectedFile && "border-success bg-success/5"
            )}
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
          >
            <input
              ref={inputRef}
              type="file"
              accept=".doc,.docx,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
              onChange={handleChange}
              className="hidden"
            />

            <div className="flex flex-col items-center text-center space-y-4">
              {selectedFile ? (
                <>
                  <div className="w-16 h-16 rounded-full bg-success/10 flex items-center justify-center">
                    <Check className="w-8 h-8 text-success" />
                  </div>
                  <div>
                    <p className="font-medium text-foreground">{selectedFile.name}</p>
                    <p className="text-sm text-muted-foreground mt-1">
                      {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
                    </p>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => inputRef.current?.click()}
                  >
                    Choose Different File
                  </Button>
                </>
              ) : (
                <>
                  <div className={cn(
                    "w-16 h-16 rounded-full flex items-center justify-center transition-all duration-200",
                    dragActive ? "bg-primary/20 scale-110" : "bg-primary/10"
                  )}>
                    {dragActive ? (
                      <Upload className="w-8 h-8 text-primary animate-bounce" />
                    ) : (
                      <FileText className="w-8 h-8 text-primary" />
                    )}
                  </div>
                  <div>
                    <p className="text-lg font-medium text-foreground">
                      {dragActive ? "Drop your file here" : "Drag & drop your file"}
                    </p>
                    <p className="text-sm text-muted-foreground mt-1">
                      or{' '}
                      <button
                        onClick={() => inputRef.current?.click()}
                        className="text-primary hover:underline font-medium"
                      >
                        browse files
                      </button>
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2 justify-center">
                    <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-primary/10 text-primary">
                      .DOC
                    </span>
                    <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-primary/10 text-primary">
                      .DOCX
                    </span>
                    <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-muted text-muted-foreground opacity-50">
                      .XLS (Coming Soon)
                    </span>
                    <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-muted text-muted-foreground opacity-50">
                      .PPTX (Coming Soon)
                    </span>
                  </div>
                </>
              )}
            </div>
          </div>

          {/* Actions */}
          <div className="flex gap-3 mt-6">
            <Button
              variant="outline"
              onClick={onClose}
              className="flex-1"
            >
              Cancel
            </Button>
            <Button
              onClick={handleSubmit}
              disabled={!selectedFile}
              className="flex-1"
            >
              Open Instance
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
