import type { LeadOut } from '@/types/leads'

type LeadCardProps = {
  lead: LeadOut
  onClick: () => void
}

const LeadCard = ({ lead, onClick }: LeadCardProps) => (
  <button
    type="button"
    data-testid="lead-card"
    onClick={onClick}
    style={{
      textAlign: 'left',
      padding: '10px 12px',
      borderRadius: 8,
      border: '1px solid var(--color-border)',
      background: 'var(--color-bg)',
      color: 'var(--color-text)',
      fontSize: 13.5,
      fontWeight: 500,
    }}
  >
    {lead.name ?? 'Sin nombre'}
  </button>
)

export default LeadCard
