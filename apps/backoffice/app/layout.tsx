import type { Metadata } from 'next'
import { Geist, Geist_Mono } from 'next/font/google'
import './globals.css'
import { LeadsRuntimeProvider } from '@/lib/LeadsRuntimeProvider'

const geistSans = Geist({
  subsets: ['latin'],
  variable: '--font-geist',
})

const geistMono = Geist_Mono({
  subsets: ['latin'],
  variable: '--font-geist-mono',
})

export const metadata: Metadata = {
  title: 'DMC BackOffice — Calificación de Leads',
  description: 'Panel interno para el equipo comercial de DMC Institute',
}

const RootLayout = ({ children }: { children: React.ReactNode }) => (
  <html lang="es-PE" className={`${geistSans.variable} ${geistMono.variable}`}>
    <body>
      <LeadsRuntimeProvider>{children}</LeadsRuntimeProvider>
    </body>
  </html>
)

export default RootLayout
