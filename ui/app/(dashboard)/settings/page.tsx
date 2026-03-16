'use client'

import { useWebSocket } from '@/hooks/useWebSocket'
import {
  Bell,
  HelpCircle,
  Settings,
} from 'lucide-react'

export default function SettingsPage() {
  const { status } = useWebSocket()

  return (
    <div className="h-screen flex flex-col bg-[#060a14]">
      <header className="h-16 bg-[#060a14] border-b border-white/10 flex items-center justify-between px-6">
        <div className="flex items-center gap-4">
          <h1 className="text-xl font-semibold text-white">Settings</h1>
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
        <div className="max-w-4xl mx-auto space-y-6">
          <div className="bg-white/[0.02] border border-white/10 rounded-xl p-6">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-[#39ff14]/10 flex items-center justify-center">
                <Settings className="w-5 h-5 text-[#39ff14]" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-white">Workspace Settings</h2>
                <p className="text-sm text-slate-500">
                  Configure default behavior for document planning and execution.
                </p>
              </div>
            </div>
            <div className="mt-6 text-sm text-slate-500">
              Settings UI is coming next — tell me which controls you want here first.
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
