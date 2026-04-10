import {
  ArrowRight,
  Braces,
  Code2,
  FileText,
  FolderSearch,
  Github,
  Layers,
  Replace,
  Shield,
  Sparkles,
} from 'lucide-react'

const repoUrl = 'https://github.com/enoch3712/AgenticDocs'

export default function App() {
  return (
    <div className="relative overflow-hidden bg-[#060a14] text-slate-100">
      {/* ───── Header ───── */}
      <header className="sticky top-0 z-30 border-b border-white/10 bg-[#060a14]/80 backdrop-blur-xl">
        <div className="mx-auto flex w-full max-w-7xl items-center justify-between px-6 py-4">
          <a href="/" className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-orange-500/15 border border-orange-500/30">
              <Braces className="h-5 w-5 text-orange-400" />
            </div>
            <div>
              <p className="font-heading text-lg font-semibold tracking-tight">OfficePlane</p>
              <p className="text-xs text-slate-400">Open-Source ECM</p>
            </div>
          </a>
          <div className="flex items-center gap-4">
            <a href="https://enoch3712.github.io/OfficePlane/docs/" className="hidden sm:inline text-sm text-slate-400 transition hover:text-white">
              Docs
            </a>
            <a
              href={repoUrl}
              className="inline-flex items-center gap-2 rounded-lg bg-white/5 border border-white/10 px-3 py-2 text-sm font-medium text-slate-200 transition hover:bg-white/10"
            >
              <Github className="h-4 w-4" />
              GitHub
            </a>
          </div>
        </div>
      </header>

      <main>
        {/* ───── Hero ───── */}
        <section className="relative mx-auto max-w-7xl px-6 pb-24 pt-20 sm:pt-28">
          {/* Glow effect */}
          <div className="pointer-events-none absolute -top-40 left-1/2 -translate-x-1/2 h-[500px] w-[800px] rounded-full bg-[#39ff14]/[0.04] blur-[120px]" />

          <div className="relative text-center">
            <div className="inline-flex items-center gap-2 rounded-full border border-[#39ff14]/20 bg-[#39ff14]/[0.06] px-4 py-1.5 text-xs font-medium text-[#39ff14] mb-8">
              <Sparkles className="h-3.5 w-3.5" />
              Open source &middot; MIT License
            </div>

            <h1 className="mx-auto max-w-4xl font-heading text-4xl font-semibold leading-[1.1] text-white sm:text-6xl lg:text-7xl">
              The open-source ECM for the{' '}
              <span className="text-[#39ff14]">agentic era</span>
            </h1>

            <p className="mx-auto mt-6 max-w-2xl text-lg leading-relaxed text-slate-400 sm:text-xl">
              A harness-powered document platform where AI agents read, extract, build, and verify
              documents — with the same reliability your enterprise demands.
            </p>

            <div className="mt-10 flex flex-wrap items-center justify-center gap-4">
              <a
                href={repoUrl}
                className="group inline-flex items-center gap-2 rounded-lg bg-[#39ff14] px-6 py-3.5 text-sm font-semibold text-[#060a14] transition hover:bg-[#39ff14]/90"
              >
                <Github className="h-4 w-4" />
                Get Started
                <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
              </a>
              <a
                href="https://enoch3712.github.io/OfficePlane/docs/"
                className="inline-flex items-center gap-2 rounded-lg border border-white/20 bg-white/5 px-6 py-3.5 text-sm font-semibold text-slate-100 transition hover:bg-white/10"
              >
                Read the docs
              </a>
            </div>

          </div>
        </section>

        {/* ───── Engineered for Autonomy — Bento Grid ───── */}
        <section className="mx-auto max-w-7xl px-6 pb-24">
          <div className="text-center mb-14">
            <h2 className="font-heading text-3xl font-semibold text-white sm:text-5xl">
              Engineered for <span className="italic text-[#39ff14]">Autonomy</span>
            </h2>
          </div>

          <div className="grid gap-5 md:grid-cols-3">
            {/* 01 — Harness */}
            <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-6">
              <p className="text-xs font-medium uppercase tracking-[0.15em] text-[#39ff14]/70 mb-2">01 // Harness</p>
              <h3 className="font-heading text-xl font-semibold text-white">Full lifecycle orchestration</h3>

              {/* Mini terminal visual */}
              <div className="mt-5 rounded-xl border border-white/[0.06] bg-[#0a0f1e] p-4 font-mono text-[11px] leading-[1.7]">
                <p className="text-slate-500">&gt; officeplane run pipeline.yaml</p>
                <p className="mt-1"><span className="text-[#39ff14]">●</span> <span className="text-slate-300">Read</span> <span className="text-slate-500">report.docx</span></p>
                <p><span className="text-[#39ff14]">●</span> <span className="text-slate-300">Prettify</span> <span className="text-slate-500">→ 8 chapters</span></p>
                <p><span className="text-[#39ff14]">●</span> <span className="text-slate-300">Build</span> <span className="text-slate-500">→ exec summary</span></p>
                <p><span className="text-[#39ff14]">●</span> <span className="text-slate-300">Verify</span> <span className="text-slate-500">→ 0.97</span></p>
                <p className="mt-1 text-[#39ff14]">✓ Done</p>
              </div>

              <p className="mt-4 text-sm text-slate-400">
                Read, extract, build, verify — one deterministic loop with parallel execution and rollback.
              </p>
            </div>

            {/* 02 — Skills */}
            <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-6">
              <p className="text-xs font-medium uppercase tracking-[0.15em] text-[#39ff14]/70 mb-2">02 // Skills</p>
              <h3 className="font-heading text-xl font-semibold text-white">Skills as code</h3>

              {/* Skills list visual */}
              <div className="mt-5 rounded-xl border border-white/[0.06] bg-[#0a0f1e] p-4 space-y-2">
                {['/prettify', '/build', '/verify', '/convert', '/merge'].map((s) => (
                  <div key={s} className="flex items-center gap-2">
                    <code className="rounded bg-[#39ff14]/10 px-2 py-0.5 text-[11px] font-semibold text-[#39ff14]">{s}</code>
                    <div className="h-px flex-1 bg-white/[0.06]" />
                    <span className="text-[10px] text-slate-600">ready</span>
                  </div>
                ))}
              </div>

              <p className="mt-4 text-sm text-slate-400">
                Pluggable skills your agent calls like functions. Testable, composable, version-controlled.
              </p>
            </div>

            {/* 03 — Prettify */}
            <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-6">
              <p className="text-xs font-medium uppercase tracking-[0.15em] text-[#39ff14]/70 mb-2">03 // Extraction</p>
              <h3 className="font-heading text-xl font-semibold text-white">Vision-powered prettify</h3>

              {/* JSON output visual */}
              <div className="mt-5 rounded-xl border border-white/[0.06] bg-[#0a0f1e] p-4 font-mono text-[11px] leading-[1.6]">
                <p><span className="text-slate-500">{'{'}</span></p>
                <p className="pl-3"><span className="text-[#39ff14]">"chapters"</span><span className="text-slate-500">:</span> <span className="text-purple-400">8</span><span className="text-slate-500">,</span></p>
                <p className="pl-3"><span className="text-[#39ff14]">"sections"</span><span className="text-slate-500">:</span> <span className="text-purple-400">23</span><span className="text-slate-500">,</span></p>
                <p className="pl-3"><span className="text-[#39ff14]">"pages"</span><span className="text-slate-500">:</span> <span className="text-purple-400">42</span><span className="text-slate-500">,</span></p>
                <p className="pl-3"><span className="text-[#39ff14]">"confidence"</span><span className="text-slate-500">:</span> <span className="text-purple-400">0.98</span></p>
                <p><span className="text-slate-500">{'}'}</span></p>
              </div>

              <p className="mt-4 text-sm text-slate-400">
                Any DOCX, PDF, PPTX → structured, machine-readable output. Deterministic, every time.
              </p>
            </div>

            {/* 04 — Full ECM */}
            <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-6">
              <p className="text-xs font-medium uppercase tracking-[0.15em] text-[#39ff14]/70 mb-2">04 // Foundation</p>
              <h3 className="font-heading text-xl font-semibold text-white">Full ECM</h3>

              {/* Feature badges visual */}
              <div className="mt-5 rounded-xl border border-white/[0.06] bg-[#0a0f1e] p-4">
                <div className="flex items-center gap-2 mb-3">
                  <div className="h-8 w-8 rounded-lg bg-[#39ff14]/10 flex items-center justify-center">
                    <FileText className="h-4 w-4 text-[#39ff14]" />
                  </div>
                  <div className="h-8 w-8 rounded-lg bg-[#39ff14]/10 flex items-center justify-center">
                    <Shield className="h-4 w-4 text-[#39ff14]" />
                  </div>
                  <div className="h-8 w-8 rounded-lg bg-[#39ff14]/10 flex items-center justify-center">
                    <FolderSearch className="h-4 w-4 text-[#39ff14]" />
                  </div>
                  <div className="h-8 w-8 rounded-lg bg-[#39ff14]/10 flex items-center justify-center">
                    <Layers className="h-4 w-4 text-[#39ff14]" />
                  </div>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {['ECM', 'COMPLIANCE', 'AUDIT'].map((t) => (
                    <span key={t} className="rounded-full bg-white/5 border border-white/10 px-2.5 py-0.5 text-[10px] font-medium text-slate-400">{t}</span>
                  ))}
                </div>
              </div>

              <p className="mt-4 text-sm text-slate-400">
                Governance and compliance features built into the core engine. Not bolted on — native.
              </p>
            </div>

            {/* 05 — Drivers */}
            <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-6">
              <p className="text-xs font-medium uppercase tracking-[0.15em] text-[#39ff14]/70 mb-2">05 // Drivers</p>
              <h3 className="font-heading text-xl font-semibold text-white">Run anywhere</h3>

              {/* Driver swap visual */}
              <div className="mt-5 rounded-xl border border-white/[0.06] bg-[#0a0f1e] p-4 font-mono text-[11px] leading-[1.7]">
                <p className="text-slate-500"># Swap backends, same API</p>
                <p><span className="text-slate-200">plane</span> = <span className="text-yellow-300">OfficePlane</span>(</p>
                <p className="pl-3">driver=<span className="text-orange-400">"libreoffice"</span></p>
                <p>)</p>
                <p className="mt-1 text-slate-600"># or "google_docs"</p>
                <p className="text-slate-600"># or "microsoft_office"</p>
              </div>

              <p className="mt-4 text-sm text-slate-400">
                LibreOffice, Google Docs, Microsoft Office. Same code, different backend. Swap in one line.
              </p>
            </div>

            {/* 06 — Verification */}
            <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-6">
              <p className="text-xs font-medium uppercase tracking-[0.15em] text-[#39ff14]/70 mb-2">06 // Reliability</p>
              <h3 className="font-heading text-xl font-semibold text-white">Schema verification</h3>

              {/* Verification visual */}
              <div className="mt-5 rounded-xl border border-white/[0.06] bg-[#0a0f1e] p-4 font-mono text-[11px] leading-[1.7]">
                <p><span className="text-[#39ff14]">✓</span> <span className="text-slate-400">Page count ≤ 2</span></p>
                <p><span className="text-[#39ff14]">✓</span> <span className="text-slate-400">KPI tables present</span></p>
                <p><span className="text-[#39ff14]">✓</span> <span className="text-slate-400">Source chapters matched</span></p>
                <p><span className="text-[#39ff14]">✓</span> <span className="text-slate-400">Schema validated</span></p>
                <p className="mt-2 text-[#39ff14] font-semibold">Confidence: 0.97</p>
              </div>

              <p className="mt-4 text-sm text-slate-400">
                Every output is verified against the schema. Confidence scoring and audit trails included.
              </p>
            </div>
          </div>
        </section>

        {/* ───── Terminal / Harness Demo ───── */}
        <section className="mx-auto max-w-7xl px-6 pb-24">
          <div className="mb-10">
            <h2 className="font-heading text-3xl font-semibold text-white sm:text-4xl">
              See the harness <span className="text-[#39ff14]">in action</span>
            </h2>
            <p className="mt-4 max-w-2xl text-lg text-slate-400">
              One command kicks off the full pipeline — extract structure, build deliverables in parallel,
              verify against the schema. The harness handles the rest.
            </p>
          </div>
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

            <div className="p-6 font-mono text-[13px] leading-[1.7] space-y-1">
              <p className="text-slate-500">Harness initialized. All checks passed.</p>

              <p className="mt-2">
                <span className="text-slate-500">&gt;</span>{' '}
                <span className="text-white bg-white/10 px-1.5 py-0.5 rounded">/prettify Q4-board-deck.docx</span>
              </p>

              <p className="mt-3">
                <span className="text-[#39ff14]">●</span>{' '}
                <span className="text-white font-semibold">Prettify</span>
                <span className="text-slate-400"> — extracting document structure</span>
              </p>
              <p className="text-slate-500 pl-4">└ 42 pages, 8 chapters, 23 sections detected</p>

              <p className="mt-2">
                <span className="text-slate-500">&gt;</span>{' '}
                <span className="text-white bg-white/10 px-1.5 py-0.5 rounded">/build exec-summary --from chapters[0:3] --max-pages 2</span>
              </p>

              <p className="mt-3">
                <span className="text-[#39ff14]">●</span>{' '}
                <span className="text-white font-semibold">Build</span>
                <span className="text-slate-400"> — planning deliverable</span>
              </p>
              <p className="text-slate-500 pl-4">└ Schema: 2 pages, 12 actions, 3 verification rules</p>

              <p className="mt-2">
                <span className="text-[#39ff14]">●</span>{' '}
                <span className="text-slate-200">Launching parallel tasks:</span>
              </p>
              <div className="pl-4 space-y-0.5">
                <p><span className="text-slate-400">├</span> <span className="text-white">Extract</span> <span className="text-slate-500">KPI tables from chapters 1-3</span></p>
                <p><span className="text-slate-400">├</span> <span className="text-white">Build</span> <span className="text-slate-500">narrative summary (max 400 words)</span></p>
                <p><span className="text-slate-400">└</span> <span className="text-white">Assemble</span> <span className="text-slate-500">final document via LibreOffice driver</span></p>
              </div>

              <p className="mt-3">
                <span className="text-[#39ff14]">●</span>{' '}
                <span className="text-white font-semibold">Verify</span>
                <span className="text-slate-400"> — checking against schema</span>
              </p>
              <div className="pl-4 space-y-0.5 text-xs">
                <p><span className="text-[#39ff14]">✓</span> <span className="text-slate-400">Page count ≤ 2</span></p>
                <p><span className="text-[#39ff14]">✓</span> <span className="text-slate-400">KPI tables present</span></p>
                <p><span className="text-[#39ff14]">✓</span> <span className="text-slate-400">Content matches source chapters</span></p>
              </div>

              <div className="mt-3 rounded-lg border border-[#39ff14]/20 bg-[#39ff14]/[0.05] px-4 py-3">
                <p className="text-[#39ff14] font-semibold text-xs">
                  ✓ Done — exec-summary.docx delivered &middot; Confidence: 0.97
                </p>
              </div>

              <p className="mt-2">
                <span className="text-slate-500">&gt;</span>{' '}
                <span className="inline-block h-4 w-2 animate-pulse bg-white/70" />
              </p>
            </div>
          </div>
        </section>

        {/* ───── Code Example ───── */}
        <section className="mx-auto max-w-7xl px-6 pb-24">
          <div className="grid gap-8 lg:grid-cols-2 lg:items-center">
            <div>
              <h2 className="font-heading text-3xl font-semibold text-white sm:text-4xl">
                Five lines to document intelligence
              </h2>
              <p className="mt-4 text-lg leading-relaxed text-slate-400">
                Initialize, extract, build. OfficePlane's SDK gives your agent full document
                capabilities in a few lines of Python. The harness handles orchestration,
                the skills handle execution.
              </p>
              <div className="mt-6 space-y-3">
                <div className="flex items-start gap-3">
                  <div className="mt-0.5 rounded-lg bg-[#39ff14]/10 p-1.5">
                    <Code2 className="h-4 w-4 text-[#39ff14]" />
                  </div>
                  <div>
                    <p className="font-medium text-white">Declare intent, not steps</p>
                    <p className="text-sm text-slate-400">Let the harness figure out the execution graph</p>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <div className="mt-0.5 rounded-lg bg-[#39ff14]/10 p-1.5">
                    <Shield className="h-4 w-4 text-[#39ff14]" />
                  </div>
                  <div>
                    <p className="font-medium text-white">Built-in verification</p>
                    <p className="text-sm text-slate-400">Every result comes with a confidence score</p>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <div className="mt-0.5 rounded-lg bg-[#39ff14]/10 p-1.5">
                    <Replace className="h-4 w-4 text-[#39ff14]" />
                  </div>
                  <div>
                    <p className="font-medium text-white">Swap drivers, keep the code</p>
                    <p className="text-sm text-slate-400">LibreOffice today, Google Docs tomorrow</p>
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
              <div className="overflow-x-auto p-5">
                <pre className="text-[13px] leading-[1.8]">
                  <code className="text-slate-300">
                    <span className="text-purple-400">from</span> <span className="text-[#39ff14]">officeplane</span> <span className="text-purple-400">import</span> OfficePlane{'\n\n'}
                    <span className="text-slate-500"># Initialize with a driver</span>{'\n'}
                    <span className="text-slate-200">plane</span> = <span className="text-yellow-300">OfficePlane</span>(driver=<span className="text-orange-400">"libreoffice"</span>){'\n\n'}
                    <span className="text-slate-500"># Extract document structure</span>{'\n'}
                    <span className="text-slate-200">doc</span> = <span className="text-purple-400">await</span> plane.<span className="text-yellow-300">prettify</span>(<span className="text-orange-400">"report.docx"</span>){'\n'}
                    <span className="text-blue-400">print</span>(doc.chapters)  <span className="text-slate-500"># 8 chapters, 23 sections</span>{'\n\n'}
                    <span className="text-slate-500"># Build a new document from extracted structure</span>{'\n'}
                    <span className="text-slate-200">result</span> = <span className="text-purple-400">await</span> plane.<span className="text-yellow-300">build</span>({'\n'}
                    {'  '}source=doc,{'\n'}
                    {'  '}schema=<span className="text-orange-400">"exec_summary"</span>,{'\n'}
                    {'  '}rules=[<span className="text-orange-400">"max 2 pages"</span>, <span className="text-orange-400">"include KPIs"</span>]{'\n'}
                    ){'\n\n'}
                    <span className="text-blue-400">print</span>(result.confidence)  <span className="text-slate-500"># 0.97</span>{'\n'}
                    <span className="text-blue-400">print</span>(result.path)        <span className="text-slate-500"># ./output/exec-summary.docx</span>
                  </code>
                </pre>
              </div>
            </div>
          </div>
        </section>

        {/* ───── Open Source CTA ───── */}
        <section className="mx-auto max-w-7xl px-6 pb-24">
          <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-8 sm:p-12">
            <div className="text-center">
              <h2 className="mx-auto max-w-3xl font-heading text-3xl font-semibold text-white sm:text-5xl leading-tight">
                Replace your legacy ECM with something agents actually understand
              </h2>
              <p className="mx-auto mt-4 max-w-2xl text-lg text-slate-400 leading-relaxed">
                OfficePlane is open source and MIT-licensed. Star the repo, run it locally,
                contribute skills, and help build the ECM that the agentic era deserves.
              </p>
              <div className="mt-8 flex flex-wrap items-center justify-center gap-4">
                <a
                  href={repoUrl}
                  className="group inline-flex items-center gap-2 rounded-lg bg-[#39ff14] px-6 py-3.5 text-sm font-semibold text-[#060a14] transition hover:bg-[#39ff14]/90"
                >
                  <Github className="h-4 w-4" />
                  Star on GitHub
                  <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
                </a>
                <a
                  href={repoUrl}
                  className="inline-flex items-center gap-2 rounded-lg border border-white/20 bg-white/5 px-6 py-3.5 text-sm font-semibold text-white transition hover:bg-white/10"
                >
                  Read the docs
                </a>
              </div>
            </div>
          </div>
        </section>
      </main>

      {/* ───── Footer ───── */}
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
                  <p className="text-xs text-slate-400">Open-Source ECM</p>
                </div>
              </a>
              <p className="mt-4 max-w-xs text-sm text-slate-400">
                The open-source ECM for the agentic era. Harness-powered document intelligence, MIT-licensed.
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
                <li><a href={repoUrl} className="text-slate-400 transition hover:text-white">Skills</a></li>
                <li><a href={repoUrl} className="text-slate-400 transition hover:text-white">Drivers</a></li>
                <li><a href={repoUrl} className="text-slate-400 transition hover:text-white">Examples</a></li>
              </ul>
            </div>

            <div>
              <p className="font-semibold text-white">Community</p>
              <ul className="mt-4 space-y-2 text-sm">
                <li><a href={repoUrl} className="text-slate-400 transition hover:text-white">GitHub</a></li>
                <li><a href={repoUrl} className="text-slate-400 transition hover:text-white">Discussions</a></li>
                <li><a href={repoUrl} className="text-slate-400 transition hover:text-white">Contributing</a></li>
                <li><a href={repoUrl} className="text-slate-400 transition hover:text-white">Changelog</a></li>
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
