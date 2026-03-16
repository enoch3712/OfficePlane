import type { Metadata } from 'next'
import { IBM_Plex_Sans, Space_Grotesk } from 'next/font/google'
import './globals.css'
import { Providers } from './providers'

export const metadata: Metadata = {
  title: 'OfficePlane | Agentic Runtime For Documents',
  description:
    'Open-source agentic runtime to plan, execute, and verify document workflows across LibreOffice, Google Docs, and Microsoft Office.',
}

const bodyFont = IBM_Plex_Sans({
  subsets: ['latin'],
  variable: '--font-body',
  weight: ['400', '500', '600', '700'],
  display: 'swap',
})

const headingFont = Space_Grotesk({
  subsets: ['latin'],
  variable: '--font-heading',
  weight: ['500', '600', '700'],
  display: 'swap',
})

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body
        className={`${bodyFont.variable} ${headingFont.variable} antialiased bg-background text-foreground`}
        suppressHydrationWarning
      >
        <Providers>
          {children}
        </Providers>
      </body>
    </html>
  )
}
