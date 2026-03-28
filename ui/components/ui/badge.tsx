import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/cn'

const badgeVariants = cva(
  'inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium uppercase tracking-wider font-mono',
  {
    variants: {
      variant: {
        neutral: 'bg-depth-2 text-muted-foreground',
        accent: 'bg-primary/15 text-primary',
        warning: 'bg-amber-500/15 text-amber-400',
        error: 'bg-red-500/10 text-red-400',
        info: 'bg-blue-500/15 text-blue-400',
        success: 'bg-depth-2 text-muted-foreground',
      },
    },
    defaultVariants: {
      variant: 'neutral',
    },
  }
)

interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <span className={cn(badgeVariants({ variant }), className)} {...props} />
  )
}

export { Badge, badgeVariants }
