import type { Metadata } from 'next'
import { Cinzel, Josefin_Sans } from 'next/font/google'
import './globals.css'

const cinzel = Cinzel({
  subsets: ['latin'],
  variable: '--font-cinzel',
  weight: ['400', '500', '600', '700'],
  display: 'swap',
})

const josefinSans = Josefin_Sans({
  subsets: ['latin'],
  variable: '--font-josefin',
  weight: ['300', '400', '500', '600', '700'],
  style: ['normal', 'italic'],
  display: 'swap',
})

export const metadata: Metadata = {
  title: 'House Price Oracle — AI Prediction',
  description: 'End-to-end ML house price prediction powered by the Ames Housing dataset',
}

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="en"
      className={`${cinzel.variable} ${josefinSans.variable} h-full`}
    >
      <body className="min-h-dvh bg-[#050505] antialiased">{children}</body>
    </html>
  )
}
