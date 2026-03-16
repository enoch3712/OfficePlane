'use client'

import { HistoryPanel } from '@/components/HistoryPanel'
import { useWebSocket } from '@/hooks/useWebSocket'
import { Bell, HelpCircle } from 'lucide-react'

export default function ActivityPage() {
  const { status, events } = useWebSocket()

  return (
    <div className="h-screen flex flex-col bg-[#060a14]">
      <header className="h-16 bg-[#060a14] border-b border-white/10 flex items-center justify-between px-6">
        <div className="flex items-center gap-4">
          <h1 className="text-xl font-semibold text-white">Activity</h1>
          <div className="flex items-center gap-2">
            <div
              className={`w-2 h-2 rounded-full ${
                status === 'connected' ? 'bg-green-500' : 'bg-white/10'
              }`}
            />
            <span className="text-sm text-slate-400">
              {status === 'connected' ? 'Live' : 'Disconnected'}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <button className="p-2 hover:bg-white/5 rounded-lg transition-colors">
            <HelpCircle className="w-5 h-5 text-slate-400" />
          </button>
          <button className="p-2 hover:bg-white/5 rounded-lg transition-colors relative">
            <Bell className="w-5 h-5 text-slate-400" />
            <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-[#39ff14] rounded-full" />
          </button>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-6xl mx-auto">
          <HistoryPanel recentEvents={events} />
        </div>
      </div>
    </div>
  )
}
