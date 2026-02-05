import Link from 'next/link'
import {
  ArrowRight,
  Bot,
  Braces,
  CheckCircle2,
  Files,
  Gauge,
  Github,
  Layers,
  Orbit,
  ShieldCheck,
  Sparkles,
  Workflow,
} from 'lucide-react'

const repoUrl = 'https://github.com/enoch3712/AgenticDocs'

const capabilities = [
  {
    title: 'Plan, Execute, Verify',
    description:
      'Turn one natural-language intent into a deterministic action graph, execute it atomically, then verify outcomes against user intent.',
    icon: Workflow,
  },
  {
    title: 'Cross-Document Drivers',
    description:
      'Run the same workflow on LibreOffice, Google Docs, or Microsoft Office with provider-specific drivers behind one API surface.',
    icon: Layers,
  },
  {
    title: 'Prediction + Harness',
    description:
      'Use prediction to pre-compute likely actions and harness tools to reliably update large office files with low latency.',
    icon: Orbit,
  },
  {
    title: 'Observable By Default',
    description:
      'Track each run, each action, and each verification check. Build trust with immutable run logs and confidence scoring.',
    icon: Gauge,
  },
]

const integrations = [
  'LibreOffice Driver',
  'Google Docs Driver',
  'Microsoft 365 Driver',
  'FastAPI Runtime',
  'MCP Tooling',
  'Webhook + Queue',
]

const pricing = [
  {
    name: 'OSS',
    price: '$0',
    subtitle: 'Self-hosted core runtime',
    cta: 'Read the README',
    href: repoUrl,
    featured: false,
    points: [
      'Unlimited local agentic runs',
      'Plan-Execute-Verify API',
      'Community support',
      'Bring your own infra',
    ],
  },
  {
    name: 'Scale',
    price: '$99',
    subtitle: 'per month + usage',
    cta: 'Start with Scale',
    href: repoUrl,
    featured: true,
    points: [
      '5k included agentic actions / month',
      '$0.004 per additional action',
      'Run replay, failure recovery, and audit logs',
      'Team roles and shared projects',
    ],
  },
  {
    name: 'Enterprise',
    price: 'Custom',
    subtitle: 'private control plane',
    cta: 'Talk to us',
    href: 'mailto:founders@officeplane.ai',
    featured: false,
    points: [
      'Dedicated deployment and SSO',
      'Policy controls and data residency',
      'Premium SLAs with migration support',
      'Driver customization and onboarding',
    ],
  },
]

const flow = [
  {
    step: '01',
    title: 'Declare intent',
    detail: 'Describe the desired edit: summary decks, contract updates, policy rewrites, or bulk form fills.',
  },
  {
    step: '02',
    title: 'Generate action graph',
    detail: 'OfficePlane compiles intent into executable tool actions with dependency placeholders.',
  },
  {
    step: '03',
    title: 'Execute atomically',
    detail: 'Actions run in one transaction-like sequence to avoid partial updates across large documents.',
  },
  {
    step: '04',
    title: 'Verify outcomes',
    detail: 'A verification pass confirms intent fulfillment and returns confidence + findings.',
  },
]

export default function LandingPage() {
  return (
    <div className="relative overflow-hidden bg-[#060a14] text-slate-100">
      <div className="pointer-events-none absolute -top-48 left-1/2 h-[35rem] w-[35rem] -translate-x-1/2 rounded-full bg-[radial-gradient(circle,rgba(255,130,36,0.35),rgba(6,10,20,0))]" />
      <div className="pointer-events-none absolute right-0 top-48 h-80 w-80 rounded-full bg-[radial-gradient(circle,rgba(48,183,255,0.28),rgba(6,10,20,0))]" />
      <div className="pointer-events-none absolute left-0 top-[32rem] h-[24rem] w-[24rem] rounded-full bg-[radial-gradient(circle,rgba(255,186,102,0.2),rgba(6,10,20,0))]" />

      <header className="sticky top-0 z-30 border-b border-white/10 bg-[#060a14]/80 backdrop-blur-xl">
        <div className="mx-auto flex w-full max-w-7xl items-center justify-between px-6 py-4">
          <Link href="/" className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-orange-400 to-orange-600 shadow-lg shadow-orange-500/30">
              <Braces className="h-5 w-5 text-white" />
            </div>
            <div>
              <p className="font-heading text-lg font-semibold tracking-tight">OfficePlane</p>
              <p className="text-xs text-slate-400">Agentic Runtime</p>
            </div>
          </Link>

          <div className="flex items-center gap-3">
            <span className="hidden rounded-full border border-emerald-300/30 bg-emerald-300/10 px-3 py-1 text-xs font-medium text-emerald-200 sm:inline-flex">
              Open Source
            </span>
            <span className="rounded-full border border-orange-200/30 bg-orange-300/10 px-3 py-1 text-xs font-medium text-orange-100">
              1.5k GitHub stars
            </span>
            <Link
              href={repoUrl}
              className="inline-flex items-center gap-1 rounded-lg bg-white px-3 py-2 text-sm font-semibold text-slate-900 transition hover:bg-orange-100"
            >
              View Repo
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        </div>
      </header>

      <main>
        <section className="relative mx-auto max-w-7xl px-6 pb-20 pt-20 sm:pt-24">
          <div className="grid items-center gap-12 lg:grid-cols-[1.1fr_0.9fr]">
            <div>
              <p className="inline-flex items-center gap-2 rounded-full border border-orange-300/30 bg-orange-300/10 px-4 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-orange-100">
                <Sparkles className="h-4 w-4" />
                Agentic behavior for office workflows
              </p>
              <h1 className="mt-6 max-w-3xl font-heading text-4xl font-semibold leading-tight text-white sm:text-6xl">
                Build agents that can
                <span className="bg-gradient-to-r from-orange-300 via-orange-200 to-sky-200 bg-clip-text text-transparent">
                  {' '}
                  reliably edit documents{' '}
                </span>
                at scale.
              </h1>
              <p className="mt-6 max-w-2xl text-lg leading-relaxed text-slate-300">
                OfficePlane is an open-source runtime for agentic actions across DOCX, PPTX, XLSX, and PDFs.
                It combines prediction, harness tooling, and verification so your AI workflows stay fast,
                deterministic, and auditable.
              </p>

              <div className="mt-8 flex flex-wrap items-center gap-4">
                <Link
                  href={repoUrl}
                  className="inline-flex items-center gap-2 rounded-xl bg-orange-500 px-5 py-3 text-sm font-semibold text-white transition hover:bg-orange-400"
                >
                  <Github className="h-4 w-4" />
                  Star on GitHub
                </Link>
                <Link
                  href={repoUrl}
                  className="inline-flex items-center gap-2 rounded-xl border border-white/20 bg-white/5 px-5 py-3 text-sm font-semibold text-slate-100 transition hover:border-white/40 hover:bg-white/10"
                >
                  Explore source
                  <ArrowRight className="h-4 w-4" />
                </Link>
              </div>

              <div className="mt-8 grid max-w-2xl gap-3 text-sm text-slate-300 sm:grid-cols-3">
                <div className="rounded-xl border border-white/10 bg-white/5 p-4">
                  <p className="text-2xl font-semibold text-white">1</p>
                  <p className="mt-1">single request for end-to-end runs</p>
                </div>
                <div className="rounded-xl border border-white/10 bg-white/5 p-4">
                  <p className="text-2xl font-semibold text-white">50%</p>
                  <p className="mt-1">faster native driver path</p>
                </div>
                <div className="rounded-xl border border-white/10 bg-white/5 p-4">
                  <p className="text-2xl font-semibold text-white">100%</p>
                  <p className="mt-1">traceable actions and outcomes</p>
                </div>
              </div>
            </div>

            <div className="relative">
              <div className="absolute inset-0 rounded-3xl bg-gradient-to-br from-orange-500/30 via-sky-400/20 to-transparent blur-3xl" />
              <div className="relative overflow-hidden rounded-3xl border border-white/15 bg-slate-950/80 p-6 shadow-2xl shadow-orange-500/15">
                <div className="mb-5 flex items-center gap-2 text-xs text-slate-300">
                  <span className="h-2.5 w-2.5 rounded-full bg-emerald-400" />
                  Live run preview
                </div>
                <div className="space-y-3 text-sm">
                  <div className="rounded-xl border border-white/10 bg-white/5 p-3">
                    <p className="text-xs uppercase tracking-[0.1em] text-slate-400">Intent</p>
                    <p className="mt-1 text-slate-100">"Update Q4 deck and summarize changes into an exec brief."</p>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="rounded-xl border border-white/10 bg-white/5 p-3">
                      <p className="text-xs uppercase tracking-[0.1em] text-slate-400">Actions</p>
                      <p className="mt-1 text-xl font-semibold text-white">24</p>
                    </div>
                    <div className="rounded-xl border border-white/10 bg-white/5 p-3">
                      <p className="text-xs uppercase tracking-[0.1em] text-slate-400">Latency</p>
                      <p className="mt-1 text-xl font-semibold text-white">1.1s</p>
                    </div>
                  </div>
                  <div className="rounded-xl border border-emerald-300/25 bg-emerald-300/10 p-3">
                    <p className="inline-flex items-center gap-2 text-emerald-200">
                      <CheckCircle2 className="h-4 w-4" />
                      Verification passed with 0.97 confidence
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-7xl px-6 pb-20">
          <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-6">
            <p className="text-xs uppercase tracking-[0.16em] text-slate-400">Built for modern document stacks</p>
            <div className="mt-5 flex flex-wrap gap-3">
              {integrations.map((item) => (
                <span
                  key={item}
                  className="inline-flex items-center rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200"
                >
                  {item}
                </span>
              ))}
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-7xl px-6 pb-24">
          <div className="mb-10 max-w-3xl">
            <p className="text-xs uppercase tracking-[0.16em] text-slate-400">Core capabilities</p>
            <h2 className="mt-3 font-heading text-3xl font-semibold text-white sm:text-4xl">
              Temporal-grade reliability, purpose-built for agentic document behavior.
            </h2>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            {capabilities.map((capability) => {
              const Icon = capability.icon
              return (
                <article
                  key={capability.title}
                  className="rounded-2xl border border-white/10 bg-gradient-to-br from-white/10 to-white/[0.03] p-6"
                >
                  <div className="inline-flex rounded-xl bg-orange-400/20 p-2 text-orange-200">
                    <Icon className="h-5 w-5" />
                  </div>
                  <h3 className="mt-4 text-xl font-semibold text-white">{capability.title}</h3>
                  <p className="mt-3 leading-relaxed text-slate-300">{capability.description}</p>
                </article>
              )
            })}
          </div>
        </section>

        <section className="mx-auto max-w-7xl px-6 pb-24">
          <div className="mb-10 max-w-3xl">
            <p className="text-xs uppercase tracking-[0.16em] text-slate-400">Execution flow</p>
            <h2 className="mt-3 font-heading text-3xl font-semibold text-white sm:text-4xl">
              One declarative call. Full runtime lifecycle.
            </h2>
          </div>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {flow.map((item) => (
              <article key={item.step} className="rounded-2xl border border-white/10 bg-white/[0.03] p-5">
                <p className="text-xs font-semibold uppercase tracking-[0.12em] text-orange-200">{item.step}</p>
                <h3 className="mt-3 text-lg font-semibold text-white">{item.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-slate-300">{item.detail}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="mx-auto max-w-7xl px-6 pb-24">
          <div className="mb-10 flex flex-wrap items-end justify-between gap-4">
            <div className="max-w-3xl">
              <p className="text-xs uppercase tracking-[0.16em] text-slate-400">Pricing model</p>
              <h2 className="mt-3 font-heading text-3xl font-semibold text-white sm:text-4xl">
                Start open source. Pay for production-grade agentic runs.
              </h2>
            </div>
            <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-2 text-xs text-slate-300">
              <Bot className="h-4 w-4 text-orange-200" />
              Usage billed by executed action volume
            </div>
          </div>
          <div className="grid gap-4 lg:grid-cols-3">
            {pricing.map((plan) => (
              <article
                key={plan.name}
                className={`rounded-2xl border p-6 ${
                  plan.featured
                    ? 'border-orange-300/50 bg-gradient-to-b from-orange-400/20 to-slate-900/70'
                    : 'border-white/10 bg-white/[0.03]'
                }`}
              >
                <p className="text-sm font-medium text-slate-300">{plan.name}</p>
                <p className="mt-3 font-heading text-4xl font-semibold text-white">{plan.price}</p>
                <p className="mt-2 text-sm text-slate-300">{plan.subtitle}</p>
                <ul className="mt-5 space-y-2 text-sm text-slate-200">
                  {plan.points.map((point) => (
                    <li key={point} className="flex items-start gap-2">
                      <ShieldCheck className="mt-0.5 h-4 w-4 flex-shrink-0 text-emerald-300" />
                      <span>{point}</span>
                    </li>
                  ))}
                </ul>
                <Link
                  href={plan.href}
                  className={`mt-6 inline-flex w-full items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold transition ${
                    plan.featured
                      ? 'bg-white text-slate-900 hover:bg-orange-100'
                      : 'border border-white/20 bg-white/5 text-white hover:border-white/40 hover:bg-white/10'
                  }`}
                >
                  {plan.cta}
                  <ArrowRight className="h-4 w-4" />
                </Link>
              </article>
            ))}
          </div>
        </section>

        <section className="mx-auto max-w-7xl px-6 pb-24">
          <div className="rounded-3xl border border-orange-300/30 bg-gradient-to-r from-orange-500/25 via-orange-400/10 to-sky-400/20 p-8 sm:p-10">
            <div className="grid gap-8 md:grid-cols-[1.2fr_0.8fr] md:items-end">
              <div>
                <p className="text-xs uppercase tracking-[0.16em] text-orange-100">Build with us</p>
                <h2 className="mt-3 max-w-2xl font-heading text-3xl font-semibold text-white sm:text-4xl">
                  Building an agentic behavior layer for every office document workflow.
                </h2>
                <p className="mt-4 max-w-2xl text-slate-100/90">
                  If you are exploring high-confidence AI automation for docs, this project is designed for you.
                  Star the repo, ship a driver, and help define the runtime standard.
                </p>
              </div>
              <div className="flex flex-wrap gap-3 md:justify-end">
                <Link
                  href={repoUrl}
                  className="inline-flex items-center gap-2 rounded-xl bg-white px-5 py-3 text-sm font-semibold text-slate-900 transition hover:bg-orange-100"
                >
                  <Github className="h-4 w-4" />
                  View repository
                </Link>
                <Link
                  href={repoUrl}
                  className="inline-flex items-center gap-2 rounded-xl border border-white/40 bg-white/10 px-5 py-3 text-sm font-semibold text-white transition hover:bg-white/20"
                >
                  Read docs
                  <Files className="h-4 w-4" />
                </Link>
              </div>
            </div>
          </div>
        </section>
      </main>
    </div>
  )
}
