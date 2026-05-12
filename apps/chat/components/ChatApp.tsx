'use client'
import Sidebar from './Sidebar'
import TopBar from './TopBar'
import Welcome from './Welcome'
import MessageList from './MessageList'
import Composer from './Composer'
import { useChat } from '@/hooks/useChat'
import { useDarkMode } from '@/hooks/useDarkMode'

const ChatApp = () => {
  const { messages, busy, sendMessage, clearMessages } = useChat()
  const { dark, toggle } = useDarkMode()
  const showWelcome = messages.length === 0

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '272px 1fr', height: '100vh', width: '100vw', background: 'var(--color-bg)' }}>
      <Sidebar dark={dark} onToggleDark={toggle} onNew={clearMessages} />
      <main style={{ display: 'flex', flexDirection: 'column', minWidth: 0, minHeight: 0, background: 'var(--color-bg)', position: 'relative' }}>
        <TopBar busy={busy} />
        {showWelcome
          ? <Welcome onPick={sendMessage} />
          : <MessageList messages={messages} />}
        <Composer onSend={sendMessage} disabled={busy} />
      </main>
    </div>
  )
}

export default ChatApp
