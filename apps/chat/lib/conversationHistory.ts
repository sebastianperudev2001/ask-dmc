import type { ConversationSummary, HistoryGroup, HistoryItem } from '@/types/chat'

const truncate = (text: string, maxLength: number): string =>
  text.length > maxLength ? `${text.slice(0, maxLength - 1)}…` : text

const isSameDay = (a: Date, b: Date): boolean =>
  a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate()

const formatTime = (date: Date): string => date.toLocaleTimeString('es-PE', { hour: '2-digit', minute: '2-digit' })

// Groups the real /conversations list into the Sidebar's Hoy/Ayer/Anteriores sections —
// replaces the hardcoded mock buckets in data/mock.ts (added after user feedback that the
// history list didn't reflect actual saved conversations). `now` is injectable for tests.
export const groupConversationsByRecency = (
  conversations: ConversationSummary[],
  activeConversationId: string | null,
  now: Date = new Date()
): HistoryGroup[] => {
  const yesterday = new Date(now)
  yesterday.setDate(yesterday.getDate() - 1)

  const today: HistoryItem[] = []
  const past: HistoryItem[] = []
  const older: HistoryItem[] = []

  for (const conversation of conversations) {
    const lastActivity = new Date(conversation.lastActivityAt)
    const item: HistoryItem = {
      id: conversation.conversationId,
      title: truncate(conversation.preview, 40),
      preview: formatTime(lastActivity),
      active: conversation.conversationId === activeConversationId,
    }
    if (isSameDay(lastActivity, now)) today.push(item)
    else if (isSameDay(lastActivity, yesterday)) past.push(item)
    else older.push(item)
  }

  return [
    { group: 'Hoy', items: today },
    { group: 'Ayer', items: past },
    { group: 'Anteriores', items: older },
  ].filter((g) => g.items.length > 0)
}
