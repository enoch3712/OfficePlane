import { cn } from '@/lib/cn'

interface LoadingStateProps {
  className?: string
  rows?: number
}

export function LoadingState({ className, rows = 3 }: LoadingStateProps) {
  return (
    <div className={cn('space-y-3', className)}>
      <div className="h-5 w-32 rounded bg-depth-2 animate-pulse" />
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="h-16 rounded-lg bg-depth-2/50 animate-pulse" />
      ))}
    </div>
  )
}
