import { LineageGraph } from '@/components/lineage/LineageGraph'
import { Card } from '@/components/ui/card'
import Link from 'next/link'
import { ArrowLeft } from 'lucide-react'

interface LineagePageProps {
  params: Promise<{
    documentId: string
  }>
}

export default async function LineagePage({ params }: LineagePageProps) {
  const { documentId } = await params

  return (
    <div className="h-[calc(100vh-4rem)] flex flex-col gap-4 -m-6 lg:-m-8 p-6 lg:p-8">
      <div className="flex items-baseline justify-between shrink-0">
        <div className="space-y-1">
          <div className="flex items-center gap-3">
            <Link
              href="/documents"
              className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              <ArrowLeft className="w-3 h-3" />
              Documents
            </Link>
          </div>
          <h1 className="text-2xl font-semibold tracking-tight">Source trail</h1>
          <p className="text-sm text-muted-foreground">
            Where every piece of this document came from, and how it evolved.
          </p>
        </div>
        <div className="text-xs font-mono text-muted-foreground opacity-50">
          doc/{documentId.slice(0, 8)}
        </div>
      </div>

      <Card className="flex-1 overflow-hidden bg-depth-1 p-0">
        <div className="h-full">
          <LineageGraph documentId={documentId} />
        </div>
      </Card>
    </div>
  )
}
