'use client'

import { useState, useEffect } from 'react'
import { formatDistanceToNow } from 'date-fns'

interface TimeAgoProps {
  date: Date | string
  addSuffix?: boolean
  className?: string
}

export function TimeAgo({ date, addSuffix = true, className }: TimeAgoProps) {
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    setMounted(true)
  }, [])

  if (!mounted) {
    // Return a placeholder during SSR to avoid hydration mismatch
    return <span className={className}>...</span>
  }

  return (
    <span className={className}>
      {formatDistanceToNow(new Date(date), { addSuffix })}
    </span>
  )
}
