import { Suspense } from 'react'
import { Editor } from '@/components/editor/Editor'
import { Card } from '@/components/ui/card'

interface EditPageProps {
  params: Promise<{ id: string }>
}

export default async function EditPage({ params }: EditPageProps) {
  const { id } = await params
  return (
    <div className="h-[calc(100vh-4rem)] flex flex-col gap-4">
      <div className="flex items-baseline justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Edit document</h1>
        <span className="text-xs font-mono text-muted-foreground">{id}</span>
      </div>
      <div className="flex-1 overflow-hidden rounded-lg border border-border bg-depth-1">
        <Suspense
          fallback={
            <div className="flex items-center justify-center h-full gap-3 text-muted-foreground">
              <div className="w-4 h-4 border-2 border-[#5EFCAB]/30 border-t-[#5EFCAB] rounded-full animate-spin" />
              <span className="text-sm font-mono">Loading...</span>
            </div>
          }
        >
          <Editor workspaceId={id} />
        </Suspense>
      </div>
    </div>
  )
}
