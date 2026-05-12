'use client'
import { useState, useEffect } from 'react'
import { Icon } from './icons'

type ThinkingBlockProps = {
  steps: string[]
  live?: boolean
}

const ThinkingBlock = ({ steps, live = false }: ThinkingBlockProps) => {
  const [open, setOpen] = useState(live)

  useEffect(() => {
    if (live) setOpen(true)
  }, [live])

  return (
    <div className={`thinking${open ? ' open' : ''}${live ? ' live' : ''}`}>
      <div className="thinking-head" onClick={() => setOpen((o) => !o)}>
        {live ? <span className="spinner" /> : <Icon name="brain" size={14} />}
        <span>{live ? 'Razonando…' : `Razonamiento (${steps.length} pasos)`}</span>
        <Icon name="chev" size={14} className="chev" />
      </div>
      {open && (
        <div className="thinking-body">
          {steps.map((s, i) => (
            <p key={i} className={live && i === steps.length - 1 ? 'pending' : ''}>{s}</p>
          ))}
        </div>
      )}
    </div>
  )
}

export default ThinkingBlock
