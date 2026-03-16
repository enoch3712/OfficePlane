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
      icon: 'bg-[#39ff14]/10 text-[#39ff14]',
      button: 'bg-[#39ff14] text-[#060a14] hover:bg-[#39ff14]/90 focus:ring-[#39ff14]/30',
    },
  }

  const styles = variantStyles[variant]

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/45 animate-in fade-in-0 duration-150"
        onClick={onClose}
      />

      {/* Dialog */}
      <div className="relative w-full max-w-md mx-4 bg-[#060a14] border border-white/10 rounded-xl shadow-xl transform-gpu animate-in fade-in-0 zoom-in-95 duration-150">
        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-1 text-slate-500 hover:text-slate-400 hover:bg-white/5 rounded-lg transition-colors"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Content */}
        <div className="p-6">
          <div className="flex items-start gap-4">
            {/* Icon */}
            <div className={cn('p-3 rounded-full', styles.icon)}>
              <AlertTriangle className="w-6 h-6" />
            </div>

            {/* Text */}
            <div className="flex-1 pt-1">
              <h3 className="text-lg font-semibold text-white">{title}</h3>
              <p className="mt-2 text-sm text-slate-400 leading-relaxed">{message}</p>
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-3 px-6 pb-6">
          <button
            onClick={onClose}
            disabled={isLoading}
            className="flex-1 px-4 py-2.5 text-sm font-medium text-slate-200 bg-white/[0.02] border border-white/10 rounded-lg hover:bg-white/5 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-white/10 transition-colors disabled:opacity-50"
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
