import type { NextConfig } from 'next'

const isGithubActions = process.env.GITHUB_ACTIONS === 'true'
const repoName = process.env.GITHUB_REPOSITORY?.split('/')[1] ?? ''
const useStaticExport = isGithubActions

const nextConfig: NextConfig = {
  reactStrictMode: true,
  output: useStaticExport ? 'export' : 'standalone',
  trailingSlash: useStaticExport,
  images: {
    unoptimized: true,
  },
  basePath: useStaticExport && repoName ? `/${repoName}` : '',
  assetPrefix: useStaticExport && repoName ? `/${repoName}/` : undefined,
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001',
    NEXT_PUBLIC_WS_URL: process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8001',
  },
  async rewrites() {
    if (useStaticExport) {
      return []
    }

    return [
      {
        source: '/api/officeplane/:path*',
        destination: `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001'}/:path*`,
      },
    ]
  },
}

export default nextConfig
