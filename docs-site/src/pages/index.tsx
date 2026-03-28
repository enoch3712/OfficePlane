import React from 'react';
import Link from '@docusaurus/Link';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import Layout from '@theme/Layout';

const FEATURES = [
  {
    num: '01',
    title: 'API Run → SSE Stream',
    description:
      'POST /api/jobs/run and watch every agent step arrive in real time. No polling — pure Server-Sent Events from queue to completion.',
    image: '/img/feature-api-run.jpg',
  },
  {
    num: '02',
    title: 'Multi-Agent Teams',
    description:
      'Decompose tasks across researcher, writer, and reviewer agents running in parallel. Redis-backed coordination with dependency tracking.',
    image: '/img/feature-multi-agent.jpg',
  },
  {
    num: '03',
    title: 'Atomic Commit',
    description:
      'Every session runs in a staging workspace. On success, all outputs commit atomically. On failure, the transaction log compensates in reverse order.',
    image: '/img/feature-atomic-commit.jpg',
  },
  {
    num: '04',
    title: 'Document Lifecycle',
    description:
      'Draft → In Review → Approved → Archived. Attach agents to lifecycle hooks for automatic compliance checks and cross-document sync.',
    image: '/img/feature-lifecycle.jpg',
  },
  {
    num: '05',
    title: 'Skill-Focused Architecture',
    description:
      'Each capability is a Python class bundling system prompt, driver selection, validation, and quality checks. Build your own or extend built-ins.',
    image: null,
    code: `class GeneratePPTXSkill(Skill):
  name = "generate-pptx-quality"
  default_driver = "deepagents_cli"

  async def run(self, ctx) -> SkillResult:
      ...
  async def quality_check(self, ctx, result):
      ...`,
  },
  {
    num: '06',
    title: 'Full ECM Surface',
    description:
      'Instances, documents, collections, search, workflows — the full ECM API surface is available and progressively backed by real implementations.',
    image: null,
    code: `POST /api/ecm/instances
GET  /api/ecm/documents/{id}
POST /api/ecm/documents/{id}/workflows
GET  /api/ecm/search?q=compliance+report
GET  /api/ecm/documents/{id}/similar`,
  },
];

function HeroSection() {
  return (
    <div className="hero--officeplane" style={{ padding: '5rem 0 4rem' }}>
      <div className="container">
        <div
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.5rem',
            background: 'rgba(57, 255, 20, 0.08)',
            border: '1px solid rgba(57, 255, 20, 0.25)',
            borderRadius: '999px',
            padding: '0.3rem 0.9rem',
            marginBottom: '1.75rem',
            fontSize: '0.8rem',
            fontFamily: 'var(--ifm-font-family-monospace)',
            color: '#39ff14',
            letterSpacing: '0.04em',
          }}
        >
          <span style={{ width: 7, height: 7, borderRadius: '50%', background: '#39ff14', display: 'inline-block' }} />
          Open Source · MIT License
        </div>

        <h1 className="hero__title-glow" style={{ fontSize: 'clamp(2.5rem, 6vw, 4.5rem)', lineHeight: 1.05 }}>
          The Open-Source<br />Agentic ECM
        </h1>

        <p className="hero__subtitle" style={{ maxWidth: 560, fontSize: '1.2rem', lineHeight: 1.65 }}>
          Plan, execute, and verify document workflows with AI agents.
          Atomic commits. Multi-agent teams. Full ECM surface — all streaming live.
        </p>

        <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center', flexWrap: 'wrap', marginTop: '2.5rem' }}>
          <Link className="hero__cta" to="/docs/overview">
            Get Started &rarr;
          </Link>
          <Link
            to="https://github.com/officeplane/officeplane"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.5rem',
              padding: '0.75rem 2rem',
              border: '1px solid #1a2236',
              borderRadius: '8px',
              color: '#e2e8f0',
              fontWeight: 600,
              textDecoration: 'none',
              transition: 'border-color 0.2s, color 0.2s',
              background: 'transparent',
            }}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLAnchorElement).style.borderColor = '#39ff14';
              (e.currentTarget as HTMLAnchorElement).style.color = '#39ff14';
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLAnchorElement).style.borderColor = '#1a2236';
              (e.currentTarget as HTMLAnchorElement).style.color = '#e2e8f0';
            }}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
            </svg>
            GitHub
          </Link>
        </div>
      </div>
    </div>
  );
}

function FeaturesSection() {
  return (
    <div style={{ background: 'linear-gradient(180deg, #0b1120 0%, #060a14 100%)', padding: '5rem 0' }}>
      <div className="container">
        <p
          style={{
            textAlign: 'center',
            color: '#39ff14',
            fontFamily: 'var(--ifm-font-family-monospace)',
            fontSize: '0.8rem',
            letterSpacing: '0.1em',
            textTransform: 'uppercase',
            marginBottom: '0.75rem',
          }}
        >
          What it does
        </p>
        <h2
          style={{
            textAlign: 'center',
            color: '#e2e8f0',
            fontFamily: 'var(--ifm-heading-font-family)',
            fontSize: 'clamp(1.75rem, 4vw, 2.5rem)',
            letterSpacing: '-0.02em',
            marginBottom: '3rem',
          }}
        >
          Engineered for Autonomy
        </h2>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
            gap: '1.5rem',
          }}
        >
          {FEATURES.map((f) => (
            <div
              key={f.num}
              style={{
                background: '#0d1525',
                border: '1px solid #1a2236',
                borderRadius: '12px',
                overflow: 'hidden',
                transition: 'border-color 0.2s, box-shadow 0.2s',
              }}
              onMouseEnter={(e) => {
                (e.currentTarget as HTMLDivElement).style.borderColor = 'rgba(57, 255, 20, 0.3)';
                (e.currentTarget as HTMLDivElement).style.boxShadow = '0 0 24px rgba(57, 255, 20, 0.06)';
              }}
              onMouseLeave={(e) => {
                (e.currentTarget as HTMLDivElement).style.borderColor = '#1a2236';
                (e.currentTarget as HTMLDivElement).style.boxShadow = 'none';
              }}
            >
              {f.image && (
                <div style={{ height: 200, overflow: 'hidden' }}>
                  <img
                    src={f.image}
                    alt={f.title}
                    style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
                  />
                </div>
              )}
              {f.code && (
                <div
                  style={{
                    background: '#060a14',
                    borderBottom: '1px solid #1a2236',
                    padding: '1.25rem 1.5rem',
                    height: 200,
                    overflow: 'hidden',
                    display: 'flex',
                    alignItems: 'center',
                  }}
                >
                  <pre
                    style={{
                      fontFamily: 'var(--ifm-font-family-monospace)',
                      fontSize: '0.75rem',
                      lineHeight: 1.65,
                      color: '#39ff14',
                      margin: 0,
                      whiteSpace: 'pre',
                    }}
                  >
                    {f.code}
                  </pre>
                </div>
              )}
              <div style={{ padding: '1.5rem' }}>
                <div
                  style={{
                    fontFamily: 'var(--ifm-font-family-monospace)',
                    fontSize: '0.7rem',
                    color: '#39ff14',
                    letterSpacing: '0.08em',
                    marginBottom: '0.5rem',
                  }}
                >
                  {f.num}
                </div>
                <h3
                  style={{
                    color: '#e2e8f0',
                    fontFamily: 'var(--ifm-heading-font-family)',
                    fontSize: '1.1rem',
                    marginBottom: '0.5rem',
                  }}
                >
                  {f.title}
                </h3>
                <p style={{ color: '#64748b', fontSize: '0.9rem', lineHeight: 1.6, margin: 0 }}>
                  {f.description}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function QuickStartSection() {
  return (
    <div style={{ background: '#060a14', padding: '5rem 0' }}>
      <div className="container" style={{ maxWidth: 760 }}>
        <p
          style={{
            textAlign: 'center',
            color: '#39ff14',
            fontFamily: 'var(--ifm-font-family-monospace)',
            fontSize: '0.8rem',
            letterSpacing: '0.1em',
            textTransform: 'uppercase',
            marginBottom: '0.75rem',
          }}
        >
          Up in 60 seconds
        </p>
        <h2
          style={{
            textAlign: 'center',
            color: '#e2e8f0',
            fontFamily: 'var(--ifm-heading-font-family)',
            fontSize: 'clamp(1.75rem, 4vw, 2.5rem)',
            letterSpacing: '-0.02em',
            marginBottom: '2.5rem',
          }}
        >
          Quick Start
        </h2>

        <div
          style={{
            background: '#0b1120',
            border: '1px solid #1a2236',
            borderRadius: '12px',
            overflow: 'hidden',
          }}
        >
          {/* window chrome */}
          <div
            style={{
              background: '#111827',
              padding: '0.75rem 1rem',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              borderBottom: '1px solid #1a2236',
            }}
          >
            {['#ef4444', '#f59e0b', '#22c55e'].map((c) => (
              <div key={c} style={{ width: 10, height: 10, borderRadius: '50%', background: c }} />
            ))}
            <span
              style={{
                fontFamily: 'var(--ifm-font-family-monospace)',
                fontSize: '0.75rem',
                color: '#475569',
                marginLeft: '0.5rem',
              }}
            >
              terminal
            </span>
          </div>

          <pre
            style={{
              padding: '1.75rem',
              margin: 0,
              fontFamily: 'var(--ifm-font-family-monospace)',
              fontSize: '0.875rem',
              lineHeight: 1.8,
              color: '#e2e8f0',
              background: 'transparent',
              overflowX: 'auto',
            }}
          >
            <span style={{ color: '#475569' }}># Clone and start{'\n'}</span>
            <span style={{ color: '#39ff14' }}>git clone</span>
            {' https://github.com/officeplane/officeplane\n'}
            <span style={{ color: '#39ff14' }}>cd</span>
            {' officeplane\n'}
            <span style={{ color: '#39ff14' }}>docker compose up -d</span>
            {'\n\n'}
            <span style={{ color: '#475569' }}># Fire off an agent job{'\n'}</span>
            <span style={{ color: '#f97316' }}>curl</span>
            {' -X POST http://localhost:8001/api/jobs/run \\\n  -d \'instruction=Generate a Q1 executive summary PPTX\'\n\n'}
            <span style={{ color: '#475569' }}># Stream the output{'\n'}</span>
            <span style={{ color: '#f97316' }}>curl</span>
            {' http://localhost:8001/api/jobs/'}
            <span style={{ color: '#94a3b8' }}>{'{job_id}'}</span>
            {'/stream'}
          </pre>
        </div>

        <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center', flexWrap: 'wrap', marginTop: '2rem' }}>
          <Link className="hero__cta" to="/docs/getting-started/quickstart">
            Full Setup Guide &rarr;
          </Link>
          <Link
            to="/docs/api/reference"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              padding: '0.75rem 2rem',
              color: '#94a3b8',
              fontWeight: 600,
              textDecoration: 'none',
              fontSize: '0.95rem',
            }}
          >
            API Reference
          </Link>
        </div>
      </div>
    </div>
  );
}

function FooterCTA() {
  return (
    <div
      style={{
        background: 'linear-gradient(180deg, #060a14 0%, #040810 100%)',
        padding: '5rem 0',
        borderTop: '1px solid #111827',
        textAlign: 'center',
      }}
    >
      <div className="container" style={{ maxWidth: 600 }}>
        <h2
          style={{
            color: '#e2e8f0',
            fontFamily: 'var(--ifm-heading-font-family)',
            fontSize: 'clamp(1.5rem, 4vw, 2.25rem)',
            letterSpacing: '-0.02em',
            marginBottom: '1rem',
          }}
        >
          Ready to automate your document workflows?
        </h2>
        <p style={{ color: '#64748b', fontSize: '1rem', lineHeight: 1.7, marginBottom: '2rem' }}>
          OfficePlane is MIT-licensed and built for teams that want AI agents
          doing real work on real documents — without black boxes.
        </p>
        <Link className="hero__cta" to="/docs/overview">
          Start Building &rarr;
        </Link>
      </div>
    </div>
  );
}

export default function Home(): React.JSX.Element {
  const { siteConfig } = useDocusaurusContext();
  return (
    <Layout
      title="The Open-Source Agentic ECM"
      description={siteConfig.tagline}
    >
      <HeroSection />
      <FeaturesSection />
      <QuickStartSection />
      <FooterCTA />
    </Layout>
  );
}
