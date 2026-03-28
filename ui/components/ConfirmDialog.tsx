'use client'

import { AlertTriangle, X, Loader2 } from 'lucide-react'
import { cn } from '@/lib/cn'

interface ConfirmDialogProps {
  isOpen: boolean
  onClose: () => void
  onConfirm: () => void
  title: string
  message: string
  confirmText?: string
  cancelText?: string
  variant?: 'danger' | 'warning' | 'default'
  isLoading?: boolean
}

export function ConfirmDialog({
  isOpen,
  onClose,
  onConfirm,
  title,
  message,
  confirmText = 'Confirm',
  cancelText = 'Cancel',
  variant = 'danger',
  isLoading = false,
}: ConfirmDialogProps) {
  if (!isOpen) return null

  const variantStyles = {
    danger: {
      icon: 'bg-red-500/10 text-red-400',
      button: 'bg-red-600 hover:bg-red-700 focus:ring-red-500',
    },
    warning: {
      icon: 'bg-amber-500/10 text-amber-400',
      button: 'bg-amber-600 hover:bg-amber-700 focus:ring-amber-500',
    },
    default: {
      icon: 'bg-primary/10 text-primary',
      button: 'bg-primary text-primary-foreground hover:bg-primary/90 focus:ring-primary/30',
    },
  }

  const styles = variantStyles[variant]

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div
        className="absolute inset-0 bg-black/45 animate-in fade-in-0 duration-150"
        onClick={onClose}
      />

      <div className="relative w-full max-w-md mx-4 bg-depth-1 border border-border rounded-xl shadow-xl transform-gpu animate-in fade-in-0 zoom-in-95 duration-150">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-1 text-muted-foreground hover:text-foreground hover:bg-depth-2 rounded-lg transition-colors"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="p-6">
          <div className="flex items-start gap-4">
            <div className={cn('p-3 rounded-full', styles.icon)}>
              <AlertTriangle className="w-6 h-6" />
            </div>

            <div className="flex-1 pt-1">
              <h3 className="font-heading text-lg font-semibold text-foreground">{title}</h3>
              <p className="mt-2 text-sm text-muted-foreground leading-relaxed">{message}</p>
            </div>
          </div>
        </div>

        <div className="flex gap-3 px-6 pb-6">
          <button
            onClick={onClose}
            disabled={isLoading}
            className="flex-1 px-4 py-2.5 text-sm font-medium text-foreground bg-depth-2 border border-border rounded-lg hover:bg-depth-3 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-border transition-colors disabled:opacity-50"
          >
            {cancelText}
          </button>
          <button
            onClick={onConfirm}
            disabled={isLoading}
            className={cn(
              'flex-1 flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-medium text-white rounded-lg focus:outline-none focus:ring-2 focus:ring-offset-2 transition-colors disabled:opacity-50',
              styles.button
            )}
          >
            {isLoading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Deleting...</span>
              </>
            ) : (
              confirmText
            )}
          </button>
        </div>
      </div>
    </div>
  )
}
