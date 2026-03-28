import { cn } from '@/lib/cn'

interface EmptyStateProps {
  icon?: React.ReactNode
  message: string
  detail?: string
  className?: string
}

export function EmptyState({ icon, message, detail, className }: EmptyStateProps) {
  return (
    <div className={cn('flex flex-col items-center justify-center py-16 text-center', className)}>
      {icon && <div className="mb-4 text-muted-foreground/40">{icon}</div>}
      <p className="text-sm text-muted-foreground">{message}</p>
      {detail && (
        <p className="mt-1 text-xs text-muted-foreground/60">{detail}</p>
      )}
    </div>
  )
}
