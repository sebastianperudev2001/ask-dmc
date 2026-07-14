'use client'
import { Icon } from './icons'
import type { HistoryGroup } from '@/types/chat'

type SidebarProps = {
  open: boolean
  dark: boolean
  onToggleDark: () => void
  onNew: () => void
  historyGroups: HistoryGroup[]
  onSelectConversation: (conversationId: string) => void
}

const Sidebar = ({ open, dark, onToggleDark, onNew, historyGroups, onSelectConversation }: SidebarProps) => {
  return (
    <aside
      style={{
        width: open ? 272 : 0,
        background: 'var(--color-surface)',
        borderRight: open ? '1px solid var(--color-border)' : 'none',
        display: 'flex',
        flexDirection: 'column',
        minHeight: 0,
        flexShrink: 0,
        overflow: 'hidden',
        transition: 'width .18s ease, border-color .18s ease',
      }}
    >
      <div style={{ width: 272, flexShrink: 0, display: 'flex', flexDirection: 'column', minHeight: 0, height: '100%' }}>
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
        {historyGroups.length === 0 && (
          <div style={{ padding: '12px 10px', fontSize: 12.5, color: 'var(--color-text-faint)' }}>
            Aún no hay conversaciones
          </div>
        )}
        {historyGroups.map((g) => (
          <div key={g.group}>
            <div style={{ padding: '12px 10px 6px', fontSize: 11, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--color-text-faint)' }}>
              {g.group}
            </div>
            {g.items.map((item) => (
              <button
                key={item.id}
                onClick={() => onSelectConversation(item.id)}
                title={item.title}
                style={{
                  width: '100%',
                  textAlign: 'left',
                  background: item.active ? 'var(--color-surface-2)' : 'transparent',
                  border: `1px solid ${item.active ? 'var(--color-border)' : 'transparent'}`,
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
      </div>
    </aside>
  )
}

export default Sidebar
