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

type Column = { key: 'hot' | 'warm' | 'cold'; label: string; leads: LeadOut[] }

type KanbanBoardProps = {
  leads: LeadOut[]
  onSelectLead: (leadId: string) => void
}

const KanbanBoard = ({ leads, onSelectLead }: KanbanBoardProps) => {
  const grouped = groupLeadsByScore(leads)
  const columns: Column[] = [
    { key: 'hot', label: 'Hot', leads: grouped.hot },
    { key: 'warm', label: 'Warm', leads: grouped.warm },
    { key: 'cold', label: 'Cold', leads: grouped.cold },
  ]

  return (
    <div style={{ display: 'flex', gap: 16, padding: 20, height: '100%', overflowX: 'auto' }}>
      {columns.map((column) => (
        <div
          key={column.key}
          data-testid={`kanban-column-${column.key}`}
          style={{
            flex: '1 1 0',
            minWidth: 260,
            display: 'flex',
            flexDirection: 'column',
            gap: 10,
            background: 'var(--color-surface)',
            border: '1px solid var(--color-border)',
            borderRadius: 10,
            padding: 12,
          }}
        >
          <div style={{ fontWeight: 600, color: 'var(--color-text)', fontSize: 13, textTransform: 'uppercase' }}>
            {column.label} <span style={{ color: 'var(--color-text-muted)' }}>({column.leads.length})</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {column.leads.map((lead) => (
              <LeadCard key={lead.id} lead={lead} onClick={() => onSelectLead(lead.id)} />
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

export default KanbanBoard
