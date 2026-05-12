'use client'
import { useState, useEffect } from 'react'

export const useDarkMode = () => {
  const [dark, setDark] = useState(false)

  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark)
  }, [dark])

  const toggle = () => setDark((d) => !d)

  return { dark, toggle }
}
