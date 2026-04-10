import React, { useState, useRef, useEffect } from 'react';
import styles from './styles.module.css';

const AI_PROVIDERS = [
  {
    name: 'ChatGPT',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
        <path
          d="M22.282 9.821a5.985 5.985 0 0 0-.516-4.91 6.046 6.046 0 0 0-6.51-2.9A6.065 6.065 0 0 0 4.981 4.18a5.985 5.985 0 0 0-3.998 2.9 6.046 6.046 0 0 0 .743 7.097 5.98 5.98 0 0 0 .51 4.911 6.051 6.051 0 0 0 6.515 2.9A5.985 5.985 0 0 0 13.26 24a6.056 6.056 0 0 0 5.772-4.206 5.99 5.99 0 0 0 3.997-2.9 6.056 6.056 0 0 0-.747-7.073zM13.26 22.43a4.476 4.476 0 0 1-2.876-1.04l.141-.081 4.779-2.758a.795.795 0 0 0 .392-.681v-6.737l2.02 1.168a.071.071 0 0 1 .038.052v5.583a4.504 4.504 0 0 1-4.494 4.494zM3.6 18.304a4.47 4.47 0 0 1-.535-3.014l.142.085 4.783 2.759a.771.771 0 0 0 .78 0l5.843-3.369v2.332a.08.08 0 0 1-.033.062L9.74 19.95a4.5 4.5 0 0 1-6.14-1.646zM2.34 7.896a4.485 4.485 0 0 1 2.366-1.973V11.6a.766.766 0 0 0 .388.676l5.815 3.355-2.02 1.168a.076.076 0 0 1-.071 0l-4.83-2.786A4.504 4.504 0 0 1 2.34 7.872zm16.597 3.855l-5.833-3.387L15.119 7.2a.076.076 0 0 1 .071 0l4.83 2.791a4.494 4.494 0 0 1-.676 8.105v-5.678a.79.79 0 0 0-.407-.667zm2.01-3.023l-.141-.085-4.774-2.782a.776.776 0 0 0-.785 0L9.409 9.23V6.897a.066.066 0 0 1 .028-.061l4.83-2.787a4.5 4.5 0 0 1 6.68 4.66zm-12.64 4.135l-2.02-1.164a.08.08 0 0 1-.038-.057V6.075a4.5 4.5 0 0 1 7.375-3.453l-.142.08L8.704 5.46a.795.795 0 0 0-.393.681zm1.097-2.365l2.602-1.5 2.607 1.5v2.999l-2.597 1.5-2.607-1.5z"
          fill="currentColor"
        />
      </svg>
    ),
    buildUrl: (title: string, url: string) =>
      `https://chatgpt.com/?hints=search&q=${encodeURIComponent(
        `Help me understand this documentation page from OfficePlane docs: "${title}". URL: ${url}`
      )}`,
    description: 'Ask questions about this page',
  },
  {
    name: 'Claude',
    icon: (
      <svg width="20" height="20" viewBox="0 0 46 32" fill="none">
        <path
          d="M28.854.573 16.58 22.364l-1.853-3.387L24.139.573h4.715Zm-10.738 0L5.463 22.689a4.547 4.547 0 0 0 2.079 6.085l6.776 3.191 2.065-3.575-5.6-2.638L21.568 5.34l-3.452-4.768ZM22.314 32l8.836-15.302 3.453 4.768-6.77 11.723-2.085.71L22.314 32Zm11.673-3.246 6.326-10.957a4.547 4.547 0 0 0-2.079-6.085L24.71 5.13l-2.065 3.575 11.247 5.3-6.326 10.957 6.42 3.792ZM40.5 5.676l-4.715.001 5.453 9.442h3.706L40.5 5.676ZM5.5 26.357l4.715-.001-5.453-9.442H1.056L5.5 26.357Z"
          fill="currentColor"
        />
      </svg>
    ),
    buildUrl: (title: string, url: string) =>
      `https://claude.ai/new?q=${encodeURIComponent(
        `Help me understand this documentation page from OfficePlane docs: "${title}". URL: ${url}`
      )}`,
    description: 'Ask questions about this page',
  },
];

interface AskAIProps {
  title?: string;
}

export default function AskAI({ title }: AskAIProps) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const defaultProvider = AI_PROVIDERS[1]; // Claude as default

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const pageUrl = typeof window !== 'undefined' ? window.location.href : '';
  const pageTitle = title || 'this page';

  return (
    <div className={styles.askAiWrapper} ref={dropdownRef}>
      <button
        className={styles.askAiButton}
        onClick={() => setIsOpen(!isOpen)}
        aria-expanded={isOpen}
        aria-haspopup="true"
      >
        <span className={styles.askAiButtonIcon}>{defaultProvider.icon}</span>
        <span className={styles.askAiButtonLabel}>Ask AI</span>
        <svg
          className={`${styles.askAiChevron} ${isOpen ? styles.askAiChevronOpen : ''}`}
          width="14"
          height="14"
          viewBox="0 0 16 16"
          fill="none"
        >
          <path
            d="M4 6l4 4 4-4"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>

      {isOpen && (
        <div className={styles.askAiDropdown}>
          {AI_PROVIDERS.map((provider) => (
            <a
              key={provider.name}
              href={provider.buildUrl(pageTitle, pageUrl)}
              target="_blank"
              rel="noopener noreferrer"
              className={styles.askAiOption}
              onClick={() => setIsOpen(false)}
            >
              <span className={styles.askAiOptionIcon}>{provider.icon}</span>
              <div className={styles.askAiOptionText}>
                <span className={styles.askAiOptionName}>
                  Open in {provider.name}
                  <svg
                    width="12"
                    height="12"
                    viewBox="0 0 16 16"
                    fill="none"
                    style={{ marginLeft: 4, opacity: 0.5 }}
                  >
                    <path
                      d="M5 3h8v8M13 3L3 13"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                </span>
                <span className={styles.askAiOptionDesc}>
                  {provider.description}
                </span>
              </div>
            </a>
          ))}
        </div>
      )}
    </div>
  );
}
