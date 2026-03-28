import * as React from 'react'
import { cn } from '@/lib/cn'

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  title?: string
  subtitle?: string
  accent?: boolean
  actions?: React.ReactNode
}

const Card = React.forwardRef<HTMLDivElement, CardProps>(
  ({ className, title, subtitle, accent, actions, children, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn(
          'rounded-lg border border-border bg-depth-1',
          accent && 'border-l-[3px] border-l-primary',
          className
        )}
        {...props}
      >
        {(title || actions) && (
          <div className="flex items-start justify-between p-5 pb-0">
            <div>
              {title && (
                <h3 className="font-heading text-sm font-semibold text-foreground">
                  {title}
                </h3>
              )}
              {subtitle && (
                <p className="mt-0.5 text-xs text-muted-foreground">{subtitle}</p>
              )}
            </div>
            {actions && <div className="flex items-center gap-2">{actions}</div>}
          </div>
        )}
        <div className="p-5">{children}</div>
      </div>
    )
  }
)
Card.displayName = 'Card'

const CardStats = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, children, ...props }, ref) => (
  <div
    ref={ref}
    className={cn(
      'rounded-lg border border-border bg-depth-1 p-5',
      className
    )}
    {...props}
  >
    {children}
  </div>
))
CardStats.displayName = 'CardStats'

interface StatItemProps {
  label: string
  value: React.ReactNode
  detail?: string
}

function StatItem({ label, value, detail }: StatItemProps) {
  return (
    <div>
      <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
        {label}
      </div>
      <div className="mt-1 text-lg font-heading font-semibold text-foreground">
        {value}
      </div>
      {detail && (
        <div className="mt-0.5 text-xs text-muted-foreground">{detail}</div>
      )}
    </div>
  )
}

export { Card, CardStats, StatItem }
