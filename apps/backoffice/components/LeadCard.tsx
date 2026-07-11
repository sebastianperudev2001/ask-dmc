import type { LeadOut } from '@/types/leads'

type LeadCardProps = {
  lead: LeadOut
  accent: string
  onClick: () => void
}

const LeadCard = ({ lead, accent, onClick }: LeadCardProps) => (
  <button
    type="button"
    data-testid="lead-card"
    onClick={onClick}
    style={{
      display: 'flex',
      alignItems: 'center',
      gap: 8,
      textAlign: 'left',
      padding: '10px 12px',
      borderRadius: 6,
      border: '1px solid var(--color-border)',
      borderLeft: `3px solid ${accent}`,
      background: 'var(--color-surface)',
      color: 'var(--color-text)',
      boxShadow: 'var(--shadow-sm)',
    }}
  >
    {lead.score === 'hot' && <span className="lead-pulse-dot" aria-hidden />}
    <span style={{ fontSize: 13.5, fontWeight: 500, fontFamily: 'var(--font-body)' }}>
      {lead.name ?? 'Sin nombre'}
    </span>
  </button>
)

export default LeadCard
