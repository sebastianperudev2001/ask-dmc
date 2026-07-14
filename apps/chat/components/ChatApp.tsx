'use client'
import { useEffect, useState } from 'react'
import Sidebar from './Sidebar'
import TopBar from './TopBar'
import Welcome from './Welcome'
import MessageList from './MessageList'
import Composer from './Composer'
import { useChat } from '@/hooks/useChat'
import { useDarkMode } from '@/hooks/useDarkMode'
import { fetchConversations, getStoredConversationId } from '@/lib/WsChatService'
import { groupConversationsByRecency } from '@/lib/conversationHistory'
import type { HistoryGroup } from '@/types/chat'

const ChatApp = () => {
  const { messages, busy, sendMessage, submitProfileData, clearMessages, switchConversation } = useChat()
  const { dark, toggle } = useDarkMode()
  const showWelcome = messages.length === 0
  const [historyGroups, setHistoryGroups] = useState<HistoryGroup[]>([])
  const [sidebarOpen, setSidebarOpen] = useState(true)

  // Real conversation history for the Sidebar — replaces the hardcoded mock list (added
  // after user feedback: "el historial... no jala las sesiones creadas?").
  useEffect(() => {
    fetchConversations().then((conversations) => {
      setHistoryGroups(groupConversationsByRecency(conversations, getStoredConversationId()))
    })
  }, [])

  return (
    <div style={{ display: 'flex', height: '100vh', width: '100vw', background: 'var(--color-bg)' }}>
      <Sidebar
        open={sidebarOpen}
        dark={dark}
        onToggleDark={toggle}
        onNew={clearMessages}
        historyGroups={historyGroups}
        onSelectConversation={switchConversation}
      />
      <main style={{ display: 'flex', flexDirection: 'column', flex: 1, minWidth: 0, minHeight: 0, background: 'var(--color-bg)', position: 'relative' }}>
        <TopBar busy={busy} sidebarOpen={sidebarOpen} onToggleSidebar={() => setSidebarOpen((o) => !o)} />
        {showWelcome
          ? <Welcome onPick={sendMessage} />
          : <MessageList messages={messages} onSubmitProfileData={submitProfileData} />}
        <Composer onSend={sendMessage} disabled={busy} />
      </main>
    </div>
  )
}

export default ChatApp
