import type { Metadata } from 'next'
import { Space_Grotesk, Inter, IBM_Plex_Mono } from 'next/font/google'
import './globals.css'
import { LeadsRuntimeProvider } from '@/lib/LeadsRuntimeProvider'

// Deliberately not Geist/Geist Mono (apps/chat's pairing) — an internal ops board reads
// differently than a consumer chat: Space Grotesk carries a technical, structural
// character for headers/labels; Inter stays neutral and dense for lead detail text;
// IBM Plex Mono marks anything that's data (scores, timestamps, status) as data.
const displayFont = Space_Grotesk({
  subsets: ['latin'],
  variable: '--font-display-loaded',
})

const bodyFont = Inter({
  subsets: ['latin'],
  variable: '--font-body-loaded',
})

const monoFont = IBM_Plex_Mono({
  subsets: ['latin'],
  weight: ['400', '500', '600'],
  variable: '--font-mono-loaded',
})

export const metadata: Metadata = {
  title: 'DMC BackOffice — Calificación de Leads',
  description: 'Panel interno para el equipo comercial de DMC Institute',
}

const RootLayout = ({ children }: { children: React.ReactNode }) => (
  <html
    lang="es-PE"
    className={`${displayFont.variable} ${bodyFont.variable} ${monoFont.variable}`}
  >
    <body>
      <LeadsRuntimeProvider>{children}</LeadsRuntimeProvider>
    </body>
  </html>
)

export default RootLayout
