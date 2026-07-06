import { describe, expect, it } from 'vitest'
import { groupConversationsByRecency } from './conversationHistory'
import type { ConversationSummary } from '@/types/chat'

describe('groupConversationsByRecency', () => {
  const now = new Date('2026-07-06T15:00:00Z')

  it('buckets conversations into Hoy/Ayer/Anteriores based on lastActivityAt', () => {
    const conversations: ConversationSummary[] = [
      { conversationId: 'today-1', preview: 'pregunta de hoy', lastActivityAt: '2026-07-06T10:00:00Z' },
      { conversationId: 'yesterday-1', preview: 'pregunta de ayer', lastActivityAt: '2026-07-05T10:00:00Z' },
      { conversationId: 'old-1', preview: 'pregunta vieja', lastActivityAt: '2026-06-01T10:00:00Z' },
    ]

    const groups = groupConversationsByRecency(conversations, null, now)

    expect(groups.map((g) => g.group)).toEqual(['Hoy', 'Ayer', 'Anteriores'])
    expect(groups[0]?.items.map((i) => i.id)).toEqual(['today-1'])
    expect(groups[1]?.items.map((i) => i.id)).toEqual(['yesterday-1'])
    expect(groups[2]?.items.map((i) => i.id)).toEqual(['old-1'])
  })

  it('omits empty groups', () => {
    const conversations: ConversationSummary[] = [
      { conversationId: 'today-1', preview: 'pregunta de hoy', lastActivityAt: '2026-07-06T10:00:00Z' },
    ]

    const groups = groupConversationsByRecency(conversations, null, now)

    expect(groups).toHaveLength(1)
    expect(groups[0]?.group).toBe('Hoy')
  })

  it('marks the active conversation and truncates long previews as the title', () => {
    const longPreview = 'a'.repeat(60)
    const conversations: ConversationSummary[] = [
      { conversationId: 'conv-1', preview: longPreview, lastActivityAt: '2026-07-06T10:00:00Z' },
    ]

    const groups = groupConversationsByRecency(conversations, 'conv-1', now)

    const item = groups[0]?.items[0]
    expect(item?.active).toBe(true)
    expect(item?.title.length).toBeLessThanOrEqual(40)
    expect(item?.title.endsWith('…')).toBe(true)
  })
})
