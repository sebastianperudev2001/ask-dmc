// camelCase wire types — translated at the boundary (lib/WsLeadsService.ts,
// components/DraftPanel.tsx) from agent-service's snake_case JSON, same pattern
// apps/chat uses in types/chat.ts.

export type LeadScore = 'hot' | 'warm' | 'cold'

export type LeadOut = {
  id: string
  createdAt: string
  name: string | null
  email: string | null
  profileSummary: string
  motivation: string
  motivationDetail: string
  recommendedPrograms: string[]
  paymentLinkSent: boolean
  paymentConfirmed: boolean
  paymentConfirmedAt: string | null
  score: LeadScore
  scoreJustification: string
}

export type DraftStatus = 'pending' | 'sent' | 'discarded'
export type DraftTrigger = 'auto' | 'on_demand'

export type OutreachDraftOut = {
  draftId: string
  leadId: string
  subject: string
  body: string
  status: DraftStatus
  trigger: DraftTrigger
  createdAt: string
  sentAt: string | null
}

// FR-14/Story 7 — synthetic id (`${leadId}-${createdAt}`), no server-issued id since
// notifications are derived client-side from lead_event, never a distinct wire message.
export type Notification = {
  id: string
  leadId: string
  leadName: string | null
  createdAt: number
}
