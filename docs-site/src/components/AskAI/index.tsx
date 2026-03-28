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
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
        <path
          d="M4.709 15.955l4.397-2.85-.537-.865-4.694 1.989a.25.25 0 0 0-.096.393l.93.933zm3.236-4.604L12.77 3.95a.25.25 0 0 0-.2-.394h-1.63a.25.25 0 0 0-.211.116L4.59 14.217l3.355-2.866zm9.164-.427L14.69 3.737a.25.25 0 0 0-.449.035l-2.024 4.748 4.892 2.404zm-4.402 3.652l4.156 2.044 2.545-2.544a.25.25 0 0 0-.096-.393l-3.92-1.66-2.685 2.553zm5.545-1.741l1.592-.674a.25.25 0 0 0 .003-.454l-1.593-.674-.002 1.802zM12.708 20.444a.25.25 0 0 0 .2-.394L8.15 12.16l-.906.774 5.03 7.456a.25.25 0 0 0 .434.054zm-4.89-5.862l-.872 1.391.574.852 1.384-.933-1.085-1.31zm8.735-4.406l-.86 1.381 1.076 1.301.872-1.392-.514-.842-.574-.448zM6.156 12.835l-.002-1.802-1.592.674a.25.25 0 0 0-.003.454l1.597.674z"
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
