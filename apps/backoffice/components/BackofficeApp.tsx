'use client'
import { useState } from 'react'
import { useLeadsSocket } from '@/hooks/useLeadsSocket'
import KanbanBoard from './KanbanBoard'
import LeadDetailModal from './LeadDetailModal'
import NotificationCenter from './NotificationCenter'

// Sole call site of useLeadsSocket() — same role ChatApp.tsx plays for useChat() in
// apps/chat. KanbanBoard/NotificationCenter never subscribe independently.
const BackofficeApp = () => {
  const { leads, notifications, dismissNotification } = useLeadsSocket()
  const [selectedLeadId, setSelectedLeadId] = useState<string | null>(null)
  const selectedLead = leads.find((l) => l.id === selectedLeadId) ?? null

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
      <header
        style={{
          padding: '14px 24px',
          borderBottom: '1px solid var(--color-border)',
          background: 'var(--color-surface)',
          display: 'flex',
          alignItems: 'baseline',
          gap: 10,
        }}
      >
        <span
          style={{
            fontFamily: 'var(--font-display)',
            fontWeight: 600,
            fontSize: 16,
            letterSpacing: '-0.01em',
          }}
        >
          BackOffice
        </span>
        <span style={{ fontSize: 12.5, color: 'var(--color-text-muted)' }}>
          Calificación de leads — DMC Institute
        </span>
      </header>

      <div style={{ flex: 1, overflow: 'hidden' }}>
        <KanbanBoard leads={leads} onSelectLead={setSelectedLeadId} />
      </div>

      <LeadDetailModal lead={selectedLead} onClose={() => setSelectedLeadId(null)} />

      <NotificationCenter
        notifications={notifications}
        onDismiss={dismissNotification}
        onNotificationClick={setSelectedLeadId}
      />
    </div>
  )
}

export default BackofficeApp
