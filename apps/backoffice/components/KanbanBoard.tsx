import type { LeadOut } from '@/types/leads'
import LeadCard from './LeadCard'

// ── Pure (exported for testing) ─────────────────────────────────────────────
export const groupLeadsByScore = (
  leads: LeadOut[]
): { hot: LeadOut[]; warm: LeadOut[]; cold: LeadOut[] } => ({
  hot: leads.filter((l) => l.score === 'hot'),
  warm: leads.filter((l) => l.score === 'warm'),
  cold: leads.filter((l) => l.score === 'cold'),
})

type Column = {
  key: 'hot' | 'warm' | 'cold'
  label: string
  leads: LeadOut[]
  accent: string
  wash: string
}

type KanbanBoardProps = {
  leads: LeadOut[]
  onSelectLead: (leadId: string) => void
}

// The board IS a heat-map: each column carries its temperature as a real background
// wash, not just a colored label — scannable at a glance, not read line by line.
const KanbanBoard = ({ leads, onSelectLead }: KanbanBoardProps) => {
  const grouped = groupLeadsByScore(leads)
  const columns: Column[] = [
    { key: 'hot', label: 'Hot', leads: grouped.hot, accent: 'var(--color-hot)', wash: 'var(--color-hot-bg)' },
    { key: 'warm', label: 'Warm', leads: grouped.warm, accent: 'var(--color-warm)', wash: 'var(--color-warm-bg)' },
    { key: 'cold', label: 'Cold', leads: grouped.cold, accent: 'var(--color-cold)', wash: 'var(--color-cold-bg)' },
  ]

  return (
    <div style={{ display: 'flex', gap: 14, padding: 20, height: '100%', overflowX: 'auto' }}>
      {columns.map((column) => (
        <div
          key={column.key}
          data-testid={`kanban-column-${column.key}`}
          style={{
            flex: '1 1 0',
            minWidth: 280,
            display: 'flex',
            flexDirection: 'column',
            gap: 10,
            background: `color-mix(in oklab, ${column.wash} 45%, var(--color-surface))`,
            border: '1px solid var(--color-border)',
            borderTop: `3px solid ${column.accent}`,
            borderRadius: 8,
            padding: '12px 12px 16px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span
              style={{
                fontFamily: 'var(--font-display)',
                fontWeight: 600,
                fontSize: 13,
                textTransform: 'uppercase',
                letterSpacing: '0.04em',
                color: column.accent,
              }}
            >
              {column.label}
            </span>
            <span
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 12,
                color: 'var(--color-text-muted)',
              }}
            >
              {column.leads.length}
            </span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {column.leads.map((lead) => (
              <LeadCard
                key={lead.id}
                lead={lead}
                accent={column.accent}
                onClick={() => onSelectLead(lead.id)}
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

export default KanbanBoard
