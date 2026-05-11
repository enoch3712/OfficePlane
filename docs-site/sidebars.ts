import type {SidebarsConfig} from '@docusaurus/plugin-content-docs';

const sidebars: SidebarsConfig = {
  docsSidebar: [
    'overview',
    {
      type: 'category',
      label: 'Getting Started',
      collapsed: false,
      items: [
        'getting-started/quickstart',
        'getting-started/installation',
        'getting-started/configuration',
      ],
    },
    {
      type: 'category',
      label: 'Architecture',
      items: [
        'architecture/overview',
        'architecture/document-tree',
        'architecture/provenance-and-lineage',
        'architecture/skills-catalog',
        'architecture/models-and-tiers',
        'architecture/file-operation-flow',
        'architecture/task-queue',
        'architecture/concurrency',
      ],
    },
    {
      type: 'category',
      label: 'Features',
      collapsed: false,
      items: [
        'features/ingestion',
        'features/plan-execute-verify',
        'features/content-generation',
        'features/generating-documents',
        'features/editing-documents',
        'features/agent-teams',
        'features/hooks',
        'features/real-time',
      ],
    },
    {
      type: 'category',
      label: 'API Reference',
      items: [
        'api-reference/endpoints',
        'api-reference/documents',
        'api-reference/instances',
        'api-reference/tasks',
        'api-reference/generation',
        'api-reference/teams',
      ],
    },
    {
      type: 'category',
      label: 'Guides',
      items: [
        'guides/upload-first-document',
        'guides/generate-presentation',
        'guides/setup-hooks',
      ],
    },
  ],
};

export default sidebars;
