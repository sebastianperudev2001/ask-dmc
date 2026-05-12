import type { Metadata } from 'next'
import { Geist, Geist_Mono } from 'next/font/google'
import './globals.css'

const geistSans = Geist({
  subsets: ['latin'],
  variable: '--font-geist',
})

const geistMono = Geist_Mono({
  subsets: ['latin'],
  variable: '--font-geist-mono',
})

export const metadata: Metadata = {
  title: 'Asesor Académico DMC',
  description: 'Orientación personalizada de cursos DMC Institute',
}

const RootLayout = ({ children }: { children: React.ReactNode }) => (
  <html lang="es-PE" className={`${geistSans.variable} ${geistMono.variable}`}>
    <body>{children}</body>
  </html>
)

export default RootLayout
