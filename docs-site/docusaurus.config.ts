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

  url: 'https://enoch3712.github.io',
  baseUrl: '/OfficePlane/docs/',

  organizationName: 'enoch3712',
  projectName: 'OfficePlane',

  onBrokenLinks: 'warn',

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
          routeBasePath: '/',
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
          to: '/api-reference/endpoints',
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
            { label: 'Overview', to: '/overview' },
            { label: 'Quick Start', to: '/getting-started/quickstart' },
            { label: 'Architecture', to: '/architecture/overview' },
          ],
        },
        {
          title: 'Features',
          items: [
            { label: 'Document Ingestion', to: '/features/ingestion' },
            { label: 'Content Generation', to: '/features/content-generation' },
            { label: 'Document Hooks', to: '/features/hooks' },
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
