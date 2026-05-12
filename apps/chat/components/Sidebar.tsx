'use client'
import { useState } from 'react'
import { Icon } from './icons'
import { HISTORY } from '@/data/mock'

type SidebarProps = {
  dark: boolean
  onToggleDark: () => void
  onNew: () => void
}

const Sidebar = ({ dark, onToggleDark, onNew }: SidebarProps) => {
  const [activeId, setActiveId] = useState('h-1')

  return (
    <aside
      style={{
        width: 272,
        background: 'var(--color-surface)',
        borderRight: '1px solid var(--color-border)',
        display: 'flex',
        flexDirection: 'column',
        minHeight: 0,
        flexShrink: 0,
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: '18px 18px 12px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 8,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, fontWeight: 600, letterSpacing: '-0.01em', color: 'var(--color-text)', fontSize: 15 }}>
          <div style={{ width: 28, height: 28, borderRadius: 8, background: 'var(--color-brand)', color: 'var(--color-brand-ink)', display: 'grid', placeItems: 'center', fontWeight: 700, fontSize: 12, letterSpacing: '0.04em' }}>
            DMC
          </div>
          <div>Asesor<span style={{ color: 'var(--color-accent-deep)', fontWeight: 500 }}> · IA</span></div>
        </div>
        <button
          onClick={onToggleDark}
          title="Cambiar tema"
          style={{ width: 32, height: 32, borderRadius: 8, border: '1px solid transparent', background: 'transparent', color: 'var(--color-text-muted)', display: 'grid', placeItems: 'center', cursor: 'pointer' }}
        >
          <Icon name={dark ? 'sun' : 'moon'} size={16} />
        </button>
      </div>

      {/* New chat */}
      <button
        onClick={onNew}
        style={{
          margin: '4px 12px 14px',
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          padding: '10px 12px',
          borderRadius: 10,
          background: 'var(--color-brand)',
          color: 'var(--color-brand-ink)',
          border: '1px solid var(--color-brand)',
          fontSize: 13.5,
          fontWeight: 500,
        }}
      >
        <Icon name="plus" size={16} />
        Nueva conversación
      </button>

      {/* History */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '4px 8px 16px', scrollbarWidth: 'thin' }}>
        {HISTORY.map((g) => (
          <div key={g.group}>
            <div style={{ padding: '12px 10px 6px', fontSize: 11, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--color-text-faint)' }}>
              {g.group}
            </div>
            {g.items.map((item) => (
              <button
                key={item.id}
                onClick={() => setActiveId(item.id)}
                title={item.title}
                style={{
                  width: '100%',
                  textAlign: 'left',
                  background: activeId === item.id ? 'var(--color-surface-2)' : 'transparent',
                  border: `1px solid ${activeId === item.id ? 'var(--color-border)' : 'transparent'}`,
                  borderRadius: 8,
                  padding: '8px 10px',
                  fontSize: 13,
                  color: 'var(--color-text)',
                  cursor: 'pointer',
                  display: 'block',
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}
              >
                {item.title}
                <div style={{ fontSize: 11.5, color: 'var(--color-text-faint)', marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {item.preview}
                </div>
              </button>
            ))}
          </div>
        ))}
      </div>

      {/* Footer */}
      <div style={{ borderTop: '1px solid var(--color-border)', padding: 12, display: 'flex', alignItems: 'center', gap: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flex: 1, minWidth: 0 }}>
          <div style={{ width: 30, height: 30, borderRadius: '50%', background: 'var(--color-surface-3)', color: 'var(--color-text)', display: 'grid', placeItems: 'center', fontSize: 12, fontWeight: 600, flexShrink: 0 }}>
            MC
          </div>
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: 13, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>María Castillo</div>
            <div style={{ fontSize: 11, color: 'var(--color-text-faint)' }}>Estudiante · Plan Anual</div>
          </div>
        </div>
        <button title="Ajustes" style={{ width: 32, height: 32, borderRadius: 8, border: '1px solid transparent', background: 'transparent', color: 'var(--color-text-muted)', display: 'grid', placeItems: 'center', cursor: 'pointer' }}>
          <Icon name="settings" size={16} />
        </button>
      </div>
    </aside>
  )
}

export default Sidebar
