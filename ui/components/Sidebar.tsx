'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
  Braces,
  FileText,
  LayoutDashboard,
  Activity,
  Settings,
  Layers,
  Clock,
  MessageSquare,
  Sparkles,
  Users,
} from 'lucide-react'
import { cn } from '@/lib/cn'
import { useWebSocket } from '@/hooks/useWebSocket'
import { StatusIndicator } from '@/components/ui/status-indicator'

const navigation = [
  { name: 'Overview', href: '/overview', icon: LayoutDashboard },
  { name: 'Documents', href: '/documents', icon: FileText },
  { name: 'Generate', href: '/generate', icon: Sparkles },
  { name: 'Teams', href: '/teams', icon: Users },
  { name: 'Chat', href: '/chat', icon: MessageSquare },
  { name: 'Instances', href: '/instances', icon: Layers },
  { name: 'Task Queue', href: '/tasks', icon: Clock },
  { name: 'Activity', href: '/activity', icon: Activity },
]

const bottomNav = [
  { name: 'Settings', href: '/settings', icon: Settings },
]

export function Sidebar() {
  const pathname = usePathname()
  const { status } = useWebSocket()

  return (
    <aside className="w-56 bg-depth-1 border-r border-border flex flex-col sticky top-0 h-screen">
      {/* Brand */}
      <div className="px-5 py-5">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 bg-primary/15 border border-primary/30 rounded-lg flex items-center justify-center">
            <Braces className="w-3.5 h-3.5 text-primary" />
          </div>
          <div>
            <span className="font-heading text-sm font-semibold text-foreground">
              OfficePlane
            </span>
            <span className="ml-1.5 text-[10px] font-mono text-muted-foreground">
              v0.1
            </span>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-2 space-y-0.5">
        {navigation.map((item) => {
          const isActive =
            pathname === item.href || pathname.startsWith(`${item.href}/`)
          const Icon = item.icon
          return (
            <Link
              key={item.name}
              href={item.href}
              className={cn(
                'flex items-center gap-3 px-5 py-2 text-sm border-l-2 transition-colors',
                isActive
                  ? 'border-l-primary text-primary font-medium'
                  : 'border-l-transparent text-muted-foreground hover:text-foreground hover:bg-depth-2'
              )}
            >
              <Icon className="w-4 h-4 flex-shrink-0" />
              <span>{item.name}</span>
            </Link>
          )
        })}
      </nav>

      {/* Bottom section */}
      <div className="border-t border-border">
        {/* Settings */}
        {bottomNav.map((item) => {
          const isActive = pathname === item.href
          const Icon = item.icon
          return (
            <Link
              key={item.name}
              href={item.href}
              className={cn(
                'flex items-center gap-3 px-5 py-2 text-sm border-l-2 transition-colors',
                isActive
                  ? 'border-l-primary text-primary font-medium'
                  : 'border-l-transparent text-muted-foreground hover:text-foreground hover:bg-depth-2'
              )}
            >
              <Icon className="w-4 h-4 flex-shrink-0" />
              <span>{item.name}</span>
            </Link>
          )
        })}

        {/* Connection status */}
        <div className="px-5 py-4">
          <StatusIndicator
            status={status === 'connected' ? 'active' : 'pending'}
            label={status === 'connected' ? 'Connected' : 'Disconnected'}
          />
        </div>
      </div>
    </aside>
  )
}
