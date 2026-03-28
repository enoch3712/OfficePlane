import {themes as prismThemes} from 'prism-react-renderer';
import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';

const config: Config = {
  title: 'OfficePlane',
  tagline: 'Agentic Runtime for Documents',
  favicon: 'img/favicon.ico',

  future: {
    v4: true,
  },

  url: 'https://officeplane.dev',
  baseUrl: '/',

  organizationName: 'officeplane',
  projectName: 'officeplane',

  onBrokenLinks: 'throw',

  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
  },

  presets: [
    [
      'classic',
      {
        docs: {
          sidebarPath: './sidebars.ts',
          editUrl: 'https://github.com/officeplane/officeplane/tree/main/docs-site/',
          routeBasePath: 'docs',
        },
        blog: false,
        theme: {
          customCss: './src/css/custom.css',
        },
      } satisfies Preset.Options,
    ],
  ],

  themeConfig: {
    image: 'img/officeplane-social.png',
    colorMode: {
      defaultMode: 'dark',
      disableSwitch: false,
      respectPrefersColorScheme: false,
    },
    navbar: {
      title: 'OfficePlane',
      logo: {
        alt: 'OfficePlane',
        src: 'img/logo.svg',
      },
      items: [
        {
          type: 'docSidebar',
          sidebarId: 'docsSidebar',
          position: 'left',
          label: 'Documentation',
        },
        {
          to: '/docs/api-reference/endpoints',
          label: 'API Reference',
          position: 'left',
        },
        {
          href: 'https://github.com/officeplane/officeplane',
          label: 'GitHub',
          position: 'right',
        },
      ],
    },
    footer: {
      style: 'dark',
      links: [
        {
          title: 'Documentation',
          items: [
            { label: 'Overview', to: '/docs/overview' },
            { label: 'Quick Start', to: '/docs/getting-started/quickstart' },
            { label: 'Architecture', to: '/docs/architecture/overview' },
          ],
        },
        {
          title: 'Features',
          items: [
            { label: 'Document Ingestion', to: '/docs/features/ingestion' },
            { label: 'Content Generation', to: '/docs/features/content-generation' },
            { label: 'Document Hooks', to: '/docs/features/hooks' },
          ],
        },
        {
          title: 'Community',
          items: [
            { label: 'GitHub', href: 'https://github.com/officeplane/officeplane' },
            { label: 'Discord', href: 'https://discord.gg/officeplane' },
          ],
        },
      ],
      copyright: `Copyright \u00a9 ${new Date().getFullYear()} OfficePlane. Built with Docusaurus.`,
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
      additionalLanguages: ['bash', 'json', 'python', 'typescript', 'yaml'],
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
