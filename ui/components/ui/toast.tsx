'use client'

import { createContext, useContext, useState, useCallback, ReactNode } from 'react'
import { X, CheckCircle2, AlertCircle, Info, FileText } from 'lucide-react'
import { cn } from '@/lib/cn'

type ToastType = 'success' | 'error' | 'info' | 'document'

interface Toast {
  id: string
  type: ToastType
  title: string
  description?: string
  details?: { label: string; value: string | number }[]
  duration?: number
}

interface ToastContextType {
  toasts: Toast[]
  addToast: (toast: Omit<Toast, 'id'>) => void
  removeToast: (id: string) => void
}

const ToastContext = createContext<ToastContextType | undefined>(undefined)

export function useToast() {
  const context = useContext(ToastContext)
  if (!context) {
    throw new Error('useToast must be used within a ToastProvider')
  }
  return context
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])

  const addToast = useCallback((toast: Omit<Toast, 'id'>) => {
    const id = Math.random().toString(36).substring(2, 9)
    const newToast = { ...toast, id }

    setToasts((prev) => [...prev, newToast])

    // Auto-remove after duration (default 5 seconds)
    const duration = toast.duration ?? 5000
    if (duration > 0) {
      setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== id))
      }, duration)
    }
  }, [])

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  return (
    <ToastContext.Provider value={{ toasts, addToast, removeToast }}>
      {children}
      <ToastContainer toasts={toasts} removeToast={removeToast} />
    </ToastContext.Provider>
  )
}

function ToastContainer({ toasts, removeToast }: { toasts: Toast[]; removeToast: (id: string) => void }) {
  return (
    <div className="fixed bottom-4 right-4 z-[100] flex flex-col gap-3 pointer-events-none">
      {toasts.map((toast) => (
        <ToastItem key={toast.id} toast={toast} onClose={() => removeToast(toast.id)} />
      ))}
    </div>
  )
}

function ToastItem({ toast, onClose }: { toast: Toast; onClose: () => void }) {
  const icons = {
    success: <CheckCircle2 className="w-5 h-5 text-emerald-400" />,
    error: <AlertCircle className="w-5 h-5 text-red-400" />,
    info: <Info className="w-5 h-5 text-blue-400" />,
    document: <FileText className="w-5 h-5 text-indigo-400" />,
  }

  const bgColors = {
    success: 'bg-emerald-500/10 border-emerald-500/20',
    error: 'bg-red-500/10 border-red-500/20',
    info: 'bg-blue-500/10 border-blue-500/20',
    document: 'bg-indigo-500/10 border-indigo-500/20',
  }

  return (
    <div
      className={cn(
        'pointer-events-auto w-80 rounded-xl border shadow-lg',
        'animate-in slide-in-from-right-full fade-in duration-300',
        bgColors[toast.type]
      )}
    >
      <div className="p-4">
        <div className="flex items-start gap-3">
          <div className="flex-shrink-0 mt-0.5">
            {icons[toast.type]}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-white">{toast.title}</p>
            {toast.description && (
              <p className="mt-1 text-sm text-slate-400">{toast.description}</p>
            )}
            {toast.details && toast.details.length > 0 && (
              <div className="mt-3 space-y-1.5">
                {toast.details.map((detail, index) => (
                  <div key={index} className="flex items-center justify-between text-sm">
                    <span className="text-slate-500">{detail.label}</span>
                    <span className="font-medium text-white">{detail.value}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
          <button
            onClick={onClose}
            className="flex-shrink-0 rounded-lg p-1.5 hover:bg-white/5 transition-colors"
          >
            <X className="w-4 h-4 text-slate-500" />
          </button>
        </div>
      </div>
    </div>
  )
}
