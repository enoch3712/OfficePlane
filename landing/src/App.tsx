import {
  ArrowRight,
  Braces,
  CheckCircle2,
  Code2,
  Files,
  Gauge,
  Github,
  Terminal,
  Workflow,
} from 'lucide-react'

const repoUrl = 'https://github.com/enoch3712/AgenticDocs'

const pricingTiers = [
  { name: 'Free', price: '$0', period: '', cta: 'Get started', ctaStyle: 'border border-white/20 bg-white/5 text-white hover:bg-white/10' },
  { name: 'Developer', price: '$9', period: '/month', cta: 'Get Developer', ctaStyle: 'bg-[#39ff14] text-[#060a14] hover:bg-[#39ff14]/90' },
  { name: 'Scaler', price: '$49', period: '/month', cta: 'Get Scaler', ctaStyle: 'bg-[#39ff14] text-[#060a14] hover:bg-[#39ff14]/90' },
  { name: 'Pro', price: '$199', period: '/month', cta: 'Get Pro', ctaStyle: 'bg-[#39ff14] text-[#060a14] hover:bg-[#39ff14]/90' },
]

const pricingRows = [
  { label: 'Actions', sub: 'Word, Excel, PowerPoint, PDF', values: ['1,000', '25,000', '200,000', '1,000,000'], overages: ['', '+ $0.0004 / action', '+ $0.0002 / action', '+ $0.0001 / action'] },
  { label: 'Prettify', sub: 'Structure extraction', values: ['500 pages', '10,000 pages', '100,000 pages', '500,000 pages'], overages: ['', '+ $0.002 / page', '+ $0.001 / page', '+ $0.0005 / page'] },
  { label: 'Contract Requests', sub: 'Plan + build + verify', values: ['50', '1,000', '10,000', '100,000'], overages: ['', '+ $0.01 / req', '+ $0.005 / req', '+ $0.002 / req'] },
  { label: 'Storage', sub: 'Documents + artifacts', values: ['1 GB', '10 GB', '50 GB', '200 GB'], overages: ['', '+ $0.50 / GB', '+ $0.25 / GB', '+ $0.10 / GB'] },
  { label: 'Drivers', sub: 'LibreOffice, Google, Microsoft', values: ['LibreOffice', 'All drivers', 'All drivers', 'All + custom'] },
  { label: 'Support', sub: '', values: ['Community', 'Email', 'Priority', 'Dedicated'] },
]

export default function App() {
  return (
    <div className="relative overflow-hidden bg-[#060a14] text-slate-100">

      {/* Header */}
      <header className="sticky top-0 z-30 border-b border-white/10 bg-[#060a14]/80 backdrop-blur-xl">
        <div className="mx-auto flex w-full max-w-7xl items-center justify-between px-6 py-4">
          <a href="/" className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-orange-500/15 border border-orange-500/30">
              <Braces className="h-5 w-5 text-orange-400" />
            </div>
            <div>
              <p className="font-heading text-lg font-semibold tracking-tight">OfficePlane</p>
              <p className="text-xs text-slate-400">Agentic Runtime</p>
            </div>
          </a>

          <a
            href={repoUrl}
            className="inline-flex items-center gap-2 rounded-lg bg-white/5 border border-white/10 px-3 py-2 text-sm font-medium text-slate-200 transition hover:bg-white/10"
          >
            <Github className="h-4 w-4" />
            GitHub
          </a>
        </div>
      </header>

      <main>
        {/* Hero */}
        <section className="relative mx-auto max-w-7xl px-6 pb-20 pt-20 sm:pt-24">
          <div className="grid items-center gap-12 lg:grid-cols-[1.1fr_0.9fr]">
            <div>
              <h1 className="max-w-3xl font-heading text-4xl font-semibold leading-[1.1] text-white sm:text-6xl">
                The agentic runtime for{' '}
                <span className="text-[#39ff14]">deterministic document workflows</span>
              </h1>
              <div className="mt-8 flex flex-wrap items-center gap-4">
                <a
                  href={repoUrl}
                  className="inline-flex items-center gap-2 rounded-lg bg-orange-500 px-5 py-3 text-sm font-semibold text-white transition hover:bg-orange-400"
                >
                  <Github className="h-4 w-4" />
                  Star on GitHub
                </a>
                <a
                  href={repoUrl}
                  className="inline-flex items-center gap-2 rounded-lg border border-white/20 bg-white/5 px-5 py-3 text-sm font-semibold text-slate-100 transition hover:bg-white/10"
                >
                  Explore source
                  <ArrowRight className="h-4 w-4" />
                </a>
              </div>
            </div>

            {/* Hero run preview */}
            <div className="overflow-hidden rounded-2xl border border-white/10 bg-white/[0.02]">
              <div className="border-b border-white/10 px-6 py-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-xs text-slate-300">
                    <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-[#39ff14]" />
                    Run #4,821 &bull; Completed
                  </div>
                  <span className="rounded-full bg-[#39ff14]/15 px-2 py-1 text-xs font-medium text-[#39ff14]">
                    SUCCESS
                  </span>
                </div>
              </div>
              <div className="p-6">
                <div className="space-y-3 text-sm">
                  <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
                    <div className="flex items-start justify-between">
                      <p className="text-xs font-semibold uppercase tracking-[0.1em] text-slate-400">Intent</p>
                      <Code2 className="h-4 w-4 text-slate-500" />
                    </div>
                    <p className="mt-2 text-slate-100 leading-relaxed">
                      &ldquo;Prettify the Q4 board deck, then build an exec summary using Contract Request&rdquo;
                    </p>
                  </div>
                  <div className="grid grid-cols-3 gap-3">
                    <div className="rounded-lg border border-white/10 bg-white/[0.03] p-3">
                      <p className="text-xs uppercase tracking-[0.1em] text-slate-400">Actions</p>
                      <p className="mt-1 text-2xl font-bold text-white">24</p>
                    </div>
                    <div className="rounded-lg border border-white/10 bg-white/[0.03] p-3">
                      <p className="text-xs uppercase tracking-[0.1em] text-slate-400">Latency</p>
                      <p className="mt-1 text-2xl font-bold text-white">1.1s</p>
                    </div>
                    <div className="rounded-lg border border-white/10 bg-white/[0.03] p-3">
                      <p className="text-xs uppercase tracking-[0.1em] text-slate-400">Pages</p>
                      <p className="mt-1 text-2xl font-bold text-white">42</p>
                    </div>
                  </div>
                  <div className="space-y-2">
                    <div className="flex items-center gap-2 text-xs text-slate-400">
                      <div className="h-px flex-1 bg-white/10" />
                      <span>Action Graph</span>
                      <div className="h-px flex-1 bg-white/10" />
                    </div>
                    <div className="space-y-1.5 text-xs">
                      <div className="flex items-center gap-2 text-slate-400">
                        <CheckCircle2 className="h-3.5 w-3.5 text-[#39ff14]" />
                        <span>Prettify &rarr; extract structure</span>
                        <span className="ml-auto text-slate-500">0.2s</span>
                      </div>
                      <div className="flex items-center gap-2 text-slate-400">
                        <CheckCircle2 className="h-3.5 w-3.5 text-[#39ff14]" />
                        <span>Contract Request &rarr; plan generation</span>
                        <span className="ml-auto text-slate-500">0.4s</span>
                      </div>
                      <div className="flex items-center gap-2 text-slate-400">
                        <CheckCircle2 className="h-3.5 w-3.5 text-[#39ff14]" />
                        <span>File assembly via LibreOffice driver</span>
                        <span className="ml-auto text-slate-500">0.3s</span>
                      </div>
                      <div className="flex items-center gap-2 text-slate-400">
                        <CheckCircle2 className="h-3.5 w-3.5 text-[#39ff14]" />
                        <span>Verify output against contract</span>
                        <span className="ml-auto text-slate-500">0.2s</span>
                      </div>
                    </div>
                  </div>
                  <div className="rounded-lg border border-[#39ff14]/20 bg-[#39ff14]/[0.07] p-4">
                    <div className="flex items-start gap-3">
                      <CheckCircle2 className="h-5 w-5 flex-shrink-0 text-[#39ff14]" />
                      <div className="flex-1">
                        <p className="font-medium text-[#39ff14]">Verification passed</p>
                        <p className="mt-1 text-xs text-[#39ff14]/70">
                          All actions completed &bull; Confidence: 0.97 &bull; Contract fulfilled
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Feature 1: Prettify */}
        <section className="mx-auto max-w-7xl px-6 pb-24">
          <div className="grid gap-10 lg:grid-cols-2 lg:items-center">
            <div>
              <h2 className="font-heading text-3xl font-semibold text-white sm:text-4xl">
                Prettify: automatic document structure detection
              </h2>
              <p className="mt-4 text-lg leading-relaxed text-slate-300">
                Point OfficePlane at any DOCX, PPTX, XLSX, or PDF. Prettify automatically detects the
                document structure—chapters, sections, pages, metadata—and returns a clean, machine-readable
                representation your agent can work with.
              </p>
              <ul className="mt-6 space-y-3 text-sm">
                <li className="flex items-start gap-3">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 flex-shrink-0 text-[#39ff14]" />
                  <span className="text-slate-300">Pick any file &rarr; run <code className="rounded bg-white/10 px-1.5 py-0.5 text-[#39ff14]">prettify()</code> &rarr; get structured output</span>
                </li>
                <li className="flex items-start gap-3">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 flex-shrink-0 text-[#39ff14]" />
                  <span className="text-slate-300">Works across all supported document formats</span>
                </li>
                <li className="flex items-start gap-3">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 flex-shrink-0 text-[#39ff14]" />
                  <span className="text-slate-300">Vision-powered extraction for complex layouts</span>
                </li>
              </ul>
            </div>
            <div className="overflow-hidden rounded-2xl bg-[#060a14]">
              <img
                src="/diagram-prettify.png"
                alt="Prettify architecture: Raw Document flows through Structure Detection and Content Extraction to produce Chapters, Sections, Pages, and Metadata"
                className="w-full"
              />
            </div>
          </div>
        </section>

        {/* Feature 2: Contract Request */}
        <section className="mx-auto max-w-7xl px-6 pb-24">
          <div className="grid gap-10 lg:grid-cols-2 lg:items-center">
            <div className="order-2 lg:order-1 overflow-hidden rounded-2xl bg-[#060a14]">
              <img
                src="/diagram-contract.png"
                alt="Contract Request architecture showing Plan, Contract, Apply flow vs traditional MCP"
                className="w-full"
              />
            </div>
            <div className="order-1 lg:order-2">
              <h2 className="font-heading text-3xl font-semibold text-white sm:text-4xl">
                Contract Request: plan, contract, apply
              </h2>
              <p className="mt-4 text-lg leading-relaxed text-slate-300">
                Instead of dozens of individual tool calls, your agent makes three moves: define a plan, lock
                it into a contract, and apply. OfficePlane validates the contract, assembles the file, and
                verifies the output—all in one deterministic pass.
              </p>
              <ul className="mt-6 space-y-3 text-sm">
                <li className="flex items-start gap-3">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 flex-shrink-0 text-[#39ff14]" />
                  <span className="text-slate-300"><strong className="text-white">Plan</strong> — agent declares intent and schema</span>
                </li>
                <li className="flex items-start gap-3">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 flex-shrink-0 text-[#39ff14]" />
                  <span className="text-slate-300"><strong className="text-white">Contract</strong> — rules, validation, expected output locked in</span>
                </li>
                <li className="flex items-start gap-3">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 flex-shrink-0 text-[#39ff14]" />
                  <span className="text-slate-300"><strong className="text-white">Apply</strong> — OfficePlane builds, verifies, delivers</span>
                </li>
              </ul>
            </div>
          </div>
        </section>

        {/* Harness Section */}
        <section className="mx-auto max-w-7xl px-6 pb-24">
          <div className="grid gap-10 lg:grid-cols-[1fr_1.2fr] lg:items-center">
            <div>
              <h2 className="font-heading text-3xl font-semibold text-white sm:text-4xl">
                Document harness as a service.{' '}
                <span className="text-[#39ff14]">For your agentic flow.</span>
              </h2>
              <p className="mt-4 text-lg leading-relaxed text-slate-300">
                Like an agent harness orchestrates tool calls and manages context across sessions—OfficePlane
                does the same for documents. Read, prettify, plan, build, verify. All in one deterministic loop
                with checkpointing, parallel execution, and contract validation.
              </p>
              <ul className="mt-6 space-y-3 text-sm">
                <li className="flex items-start gap-3">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 flex-shrink-0 text-[#39ff14]" />
                  <span className="text-slate-300">Harness manages context across long-running document workflows</span>
                </li>
                <li className="flex items-start gap-3">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 flex-shrink-0 text-[#39ff14]" />
                  <span className="text-slate-300">Parallel task execution with progress tracking and rollback</span>
                </li>
                <li className="flex items-start gap-3">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 flex-shrink-0 text-[#39ff14]" />
                  <span className="text-slate-300">Plugs into any agent framework—Claude, LangChain, CrewAI, custom</span>
                </li>
              </ul>
            </div>

            {/* Terminal UI */}
            <div className="overflow-hidden rounded-2xl border border-white/10 bg-white/[0.02]">
              <div className="flex items-center gap-2 border-b border-white/10 px-4 py-3">
                <div className="flex gap-1.5">
                  <div className="h-3 w-3 rounded-full bg-[#ff5f57]" />
                  <div className="h-3 w-3 rounded-full bg-[#febc2e]" />
                  <div className="h-3 w-3 rounded-full bg-[#28c840]" />
                </div>
                <p className="ml-2 text-xs text-slate-400 font-mono">
                  OfficePlane Harness — Q4 Board Deck Pipeline
                </p>
              </div>

              <div className="p-5 font-mono text-[13px] leading-[1.7] space-y-1">
                <p className="text-slate-500">All environment checks passed.</p>

                <p className="mt-2">
                  <span className="text-slate-500">&gt;</span>{' '}
                  <span className="text-white bg-white/10 px-1.5 py-0.5 rounded">/prettify-and-build is running…</span>
                </p>

                <p className="mt-3">
                  <span className="text-[#39ff14]">●</span>{' '}
                  <span className="text-slate-200">I&apos;ll start by reading the source documents and extracting structure.</span>
                </p>

                <p>
                  <span className="text-[#39ff14]">●</span>{' '}
                  <span className="text-white font-semibold">Read</span>
                  <span className="text-slate-400">(Q4-board-deck.docx)</span>
                </p>
                <p className="text-slate-500 pl-4">└ Read 42 pages, 8 chapters detected</p>

                <p>
                  <span className="text-[#39ff14]">●</span>{' '}
                  <span className="text-white font-semibold">Prettify</span>
                  <span className="text-slate-400">()</span>
                </p>
                <p className="text-slate-500 pl-4">└ Extracted 8 chapters, 23 sections, 156 elements</p>

                <p>
                  <span className="text-[#39ff14]">●</span>{' '}
                  <span className="text-white font-semibold">ContractRequest</span>
                  <span className="text-slate-400">(exec_summary)</span>
                </p>
                <p className="text-slate-500 pl-4">└ Plan generated: 3 deliverables, 12 actions</p>

                <p className="mt-2">
                  <span className="text-[#39ff14]">●</span>{' '}
                  <span className="text-slate-200">Launching parallel document tasks for all deliverables:</span>
                </p>

                <p>
                  <span className="text-slate-400">●</span>{' '}
                  <span className="text-white">Task</span>
                  <span className="text-slate-400">(Build executive summary — max 2 pages)</span>
                </p>
                <p>
                  <span className="text-slate-400">●</span>{' '}
                  <span className="text-white">Task</span>
                  <span className="text-slate-400">(Extract KPI tables from chapters 3-5)</span>
                </p>
                <p>
                  <span className="text-slate-400">●</span>{' '}
                  <span className="text-white">Task</span>
                  <span className="text-slate-400">(Generate charts via image service)</span>
                </p>
                <p>
                  <span className="text-slate-400">●</span>{' '}
                  <span className="text-white">Task</span>
                  <span className="text-slate-400">(Assemble final deck via LibreOffice driver)</span>
                </p>

                <p className="mt-2">
                  <span className="text-slate-500">·</span>{' '}
                  <span className="text-slate-500">Building documents for all 3 deliverables…</span>{' '}
                  <span className="text-slate-600">(esc to interrupt)</span>
                </p>
                <p className="text-slate-500 pl-4">└ Next: Verify contracts and deliver</p>

                <p className="mt-2">
                  <span className="text-slate-500">&gt;</span>{' '}
                  <span className="inline-block h-4 w-2 animate-pulse bg-white/70" />
                </p>
                <p className="text-slate-600 text-xs mt-1">? for shortcuts</p>
              </div>
            </div>
          </div>
        </section>

        {/* Code Example */}
        <section className="mx-auto max-w-7xl px-6 pb-24">
          <div className="grid gap-8 lg:grid-cols-2 lg:items-center">
            <div>
              <h2 className="font-heading text-3xl font-semibold text-white sm:text-4xl">
                One intent. Full lifecycle. Zero guesswork.
              </h2>
              <p className="mt-4 text-lg leading-relaxed text-slate-300">
                Define what you want in natural language. OfficePlane handles planning, execution, and verification—returning
                structured results with confidence scores and full action logs.
              </p>
              <div className="mt-6 space-y-3">
                <div className="flex items-start gap-3">
                  <div className="mt-0.5 rounded-lg bg-[#39ff14]/10 p-1.5">
                    <Terminal className="h-4 w-4 text-[#39ff14]" />
                  </div>
                  <div>
                    <p className="font-medium text-white">Declare intent, not steps</p>
                    <p className="text-sm text-slate-400">Let the runtime figure out the action graph</p>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <div className="mt-0.5 rounded-lg bg-[#39ff14]/10 p-1.5">
                    <Workflow className="h-4 w-4 text-[#39ff14]" />
                  </div>
                  <div>
                    <p className="font-medium text-white">Atomic execution with rollback</p>
                    <p className="text-sm text-slate-400">Never leave documents in a half-edited state</p>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <div className="mt-0.5 rounded-lg bg-[#39ff14]/10 p-1.5">
                    <Gauge className="h-4 w-4 text-[#39ff14]" />
                  </div>
                  <div>
                    <p className="font-medium text-white">Built-in verification</p>
                    <p className="text-sm text-slate-400">Confidence scoring and outcome validation included</p>
                  </div>
                </div>
              </div>
            </div>
            <div className="overflow-hidden rounded-2xl border border-white/10 bg-white/[0.02]">
              <div className="flex items-center gap-2 border-b border-white/10 px-4 py-3">
                <div className="flex gap-1.5">
                  <div className="h-3 w-3 rounded-full bg-slate-600" />
                  <div className="h-3 w-3 rounded-full bg-slate-600" />
                  <div className="h-3 w-3 rounded-full bg-slate-600" />
                </div>
                <p className="ml-2 text-xs text-slate-400">example.py</p>
              </div>
              <div className="overflow-x-auto p-4">
                <pre className="text-xs leading-relaxed">
                  <code className="text-slate-300">
                    <span className="text-purple-400">from</span> <span className="text-[#39ff14]">officeplane</span> <span className="text-purple-400">import</span> OfficePlane{'\n\n'}
                    <span className="text-slate-500"># Initialize with a driver</span>{'\n'}
                    <span className="text-slate-200">plane</span> = <span className="text-yellow-300">OfficePlane</span>(driver=<span className="text-[#39ff14]">&quot;libreoffice&quot;</span>){'\n\n'}
                    <span className="text-slate-500"># Prettify: extract document structure</span>{'\n'}
                    <span className="text-slate-200">doc</span> = <span className="text-purple-400">await</span> plane.<span className="text-yellow-300">prettify</span>(<span className="text-[#39ff14]">&quot;report.docx&quot;</span>){'\n'}
                    <span className="text-blue-400">print</span>(doc.chapters, doc.sections){'\n\n'}
                    <span className="text-slate-500"># Contract Request: agent defines the plan</span>{'\n'}
                    <span className="text-slate-200">contract</span> = plane.<span className="text-yellow-300">contract_request</span>({'\n'}
                    {'  '}schema=<span className="text-[#39ff14]">&quot;exec_summary&quot;</span>,{'\n'}
                    {'  '}source=doc,{'\n'}
                    {'  '}rules=[<span className="text-[#39ff14]">&quot;max 2 pages&quot;</span>, <span className="text-[#39ff14]">&quot;include KPIs&quot;</span>]{'\n'}
                    ){'\n\n'}
                    <span className="text-slate-500"># OfficePlane builds the file</span>{'\n'}
                    <span className="text-slate-200">result</span> = <span className="text-purple-400">await</span> plane.<span className="text-yellow-300">execute</span>(contract){'\n'}
                    <span className="text-blue-400">print</span>(f<span className="text-[#39ff14]">&quot;Confidence: </span>{'{'}result.confidence{'}'}<span className="text-[#39ff14]">&quot;</span>){'\n'}
                    <span className="text-slate-500"># Confidence: 0.97</span>
                  </code>
                </pre>
              </div>
            </div>
          </div>
        </section>

        {/* Pricing */}
        <section className="mx-auto max-w-7xl px-6 pb-24">
          <div className="mb-10">
            <h2 className="font-heading text-3xl font-semibold text-white sm:text-4xl">
              Pricing
            </h2>
            <p className="mt-3 text-lg text-slate-400">
              Self-host free forever. Managed service starts at $0.
            </p>
          </div>

          <div className="overflow-x-auto">
            <div className="min-w-[720px] rounded-2xl border border-white/10 bg-white/[0.02]">
              <div className="grid grid-cols-[1.4fr_1fr_1fr_1fr_1fr] border-b border-white/10">
                <div />
                {pricingTiers.map((tier) => (
                  <div key={tier.name} className="p-6 pb-5">
                    <p className="text-sm font-semibold text-[#39ff14]">{tier.name}</p>
                    <p className="mt-1 text-2xl font-bold text-white">
                      {tier.price}
                      {tier.period && <span className="text-sm font-normal text-slate-500">{tier.period}</span>}
                    </p>
                    <button className={`mt-4 w-full rounded-lg px-4 py-2 text-sm font-semibold transition ${tier.ctaStyle}`}>
                      {tier.cta}
                    </button>
                  </div>
                ))}
              </div>

              {pricingRows.map((row, i) => (
                <div key={row.label} className={`grid grid-cols-[1.4fr_1fr_1fr_1fr_1fr] ${i < pricingRows.length - 1 ? 'border-b border-white/[0.06]' : ''}`}>
                  <div className="p-6 py-5">
                    <p className="text-sm font-medium text-white">{row.label}</p>
                    {row.sub && <p className="text-xs text-slate-500 mt-0.5">{row.sub}</p>}
                  </div>
                  {row.values.map((val, j) => (
                    <div key={j} className="p-6 py-5">
                      <p className="text-sm text-slate-200">{val}</p>
                      {row.overages && row.overages[j] && (
                        <p className="text-xs text-slate-500 mt-0.5">{row.overages[j]}</p>
                      )}
                    </div>
                  ))}
                </div>
              ))}
            </div>
          </div>

          <div className="mt-4 flex items-center justify-between rounded-2xl border border-white/10 bg-white/[0.02] p-6">
            <div>
              <p className="text-sm font-semibold text-white">Enterprise</p>
              <p className="text-xs text-slate-500">Volume discounts, SSO, dedicated infra, custom drivers, SLA</p>
            </div>
            <a
              href="mailto:founders@officeplane.ai"
              className="rounded-lg border border-white/20 bg-white/5 px-5 py-2 text-sm font-medium text-white transition hover:bg-white/10"
            >
              Talk to us &rarr;
            </a>
          </div>
        </section>

        {/* CTA */}
        <section className="mx-auto max-w-7xl px-6 pb-24">
          <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-8 sm:p-12">
            <div className="grid gap-8 lg:grid-cols-[1.3fr_0.7fr] lg:items-center">
              <div>
                <h2 className="max-w-2xl font-heading text-3xl font-semibold text-white sm:text-5xl leading-tight">
                  Ready to build the future of document automation?
                </h2>
                <p className="mt-4 max-w-2xl text-lg text-slate-400 leading-relaxed">
                  Join the community building the agentic runtime for office workflows.
                  Star the repo, contribute drivers, and shape the future of agentic document workflows.
                </p>
                <div className="mt-8 flex flex-wrap gap-4">
                  <a
                    href={repoUrl}
                    className="group inline-flex items-center gap-2 rounded-lg bg-orange-500 px-6 py-3.5 text-sm font-semibold text-white transition hover:bg-orange-400"
                  >
                    <Github className="h-4 w-4" />
                    Star on GitHub
                    <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
                  </a>
                  <a
                    href={repoUrl}
                    className="inline-flex items-center gap-2 rounded-lg border border-white/20 bg-white/5 px-6 py-3.5 text-sm font-semibold text-white transition hover:bg-white/10"
                  >
                    Read documentation
                    <Files className="h-4 w-4" />
                  </a>
                </div>
              </div>
              <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-6">
                <p className="text-sm font-semibold text-white">Get early access to Scale tier</p>
                <p className="mt-2 text-sm text-slate-400">
                  Join the waitlist for hosted agentic runs with audit logs, team features, and premium support.
                </p>
                <div className="mt-4 space-y-3">
                  <input
                    type="email"
                    placeholder="your@email.com"
                    className="w-full rounded-lg border border-white/10 bg-white/[0.03] px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:border-[#39ff14]/50 focus:outline-none focus:ring-1 focus:ring-[#39ff14]/30"
                  />
                  <button className="w-full rounded-lg bg-orange-500 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-orange-400">
                    Join waitlist
                  </button>
                </div>
                <p className="mt-3 text-xs text-slate-500">
                  Early access includes $200 in free agentic actions
                </p>
              </div>
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-white/10">
        <div className="mx-auto max-w-7xl px-6 py-12">
          <div className="grid gap-8 md:grid-cols-[1.5fr_1fr_1fr_1fr]">
            <div>
              <a href="/" className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-orange-500/15 border border-orange-500/30">
                  <Braces className="h-5 w-5 text-orange-400" />
                </div>
                <div>
                  <p className="font-heading text-lg font-semibold tracking-tight text-white">OfficePlane</p>
                  <p className="text-xs text-slate-400">Agentic Runtime</p>
                </div>
              </a>
              <p className="mt-4 max-w-xs text-sm text-slate-400">
                Open-source runtime for reliable, deterministic document automation with AI.
              </p>
              <div className="mt-4 flex items-center gap-3">
                <a
                  href={repoUrl}
                  className="rounded-lg bg-white/5 p-2 text-slate-300 transition hover:bg-white/10 hover:text-white"
                >
                  <Github className="h-5 w-5" />
                </a>
              </div>
            </div>

            <div>
              <p className="font-semibold text-white">Product</p>
              <ul className="mt-4 space-y-2 text-sm">
                <li><a href={repoUrl} className="text-slate-400 transition hover:text-white">Documentation</a></li>
                <li><a href={repoUrl} className="text-slate-400 transition hover:text-white">Drivers</a></li>
                <li><a href={repoUrl} className="text-slate-400 transition hover:text-white">Examples</a></li>
                <li><a href={repoUrl} className="text-slate-400 transition hover:text-white">Changelog</a></li>
              </ul>
            </div>

            <div>
              <p className="font-semibold text-white">Resources</p>
              <ul className="mt-4 space-y-2 text-sm">
                <li><a href={repoUrl} className="text-slate-400 transition hover:text-white">GitHub</a></li>
                <li><a href={repoUrl} className="text-slate-400 transition hover:text-white">Community</a></li>
                <li><a href={repoUrl} className="text-slate-400 transition hover:text-white">Issues</a></li>
                <li><a href={repoUrl} className="text-slate-400 transition hover:text-white">Contributing</a></li>
              </ul>
            </div>

            <div>
              <p className="font-semibold text-white">Company</p>
              <ul className="mt-4 space-y-2 text-sm">
                <li><a href="mailto:founders@officeplane.ai" className="text-slate-400 transition hover:text-white">Contact</a></li>
                <li><a href={repoUrl} className="text-slate-400 transition hover:text-white">About</a></li>
                <li><a href={repoUrl} className="text-slate-400 transition hover:text-white">Blog</a></li>
              </ul>
            </div>
          </div>

          <div className="mt-10 border-t border-white/10 pt-8">
            <div className="flex flex-col items-center justify-between gap-4 sm:flex-row">
              <p className="text-sm text-slate-400">
                &copy; {new Date().getFullYear()} OfficePlane. Open source under MIT License.
              </p>
              <div className="flex items-center gap-6 text-sm text-slate-400">
                <a href={repoUrl} className="transition hover:text-white">Privacy</a>
                <a href={repoUrl} className="transition hover:text-white">Terms</a>
                <a href={repoUrl} className="transition hover:text-white">License</a>
              </div>
            </div>
          </div>
        </div>
      </footer>
    </div>
  )
}
