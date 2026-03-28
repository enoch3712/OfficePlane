import { cn } from '@/lib/cn'

type Status = 'active' | 'completed' | 'error' | 'pending' | 'warning'

interface StatusIndicatorProps {
  status: Status
  className?: string
  label?: string
}

const statusConfig: Record<Status, { symbol: string; className: string }> = {
  active: { symbol: '\u25CF', className: 'text-primary pulse-signal' },
  completed: { symbol: '\u2713', className: 'text-muted-foreground' },
  error: { symbol: '\u2717', className: 'text-foreground' },
  pending: { symbol: '\u25CC', className: 'text-muted-foreground' },
  warning: { symbol: '\u25C6', className: 'text-amber-400' },
}

export function StatusIndicator({ status, className, label }: StatusIndicatorProps) {
  const config = statusConfig[status]
  return (
    <span className={cn('inline-flex items-center gap-1.5', className)}>
      <span className={cn('text-xs', config.className)}>{config.symbol}</span>
      {label && (
        <span className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
          {label}
        </span>
      )}
    </span>
  )
}
