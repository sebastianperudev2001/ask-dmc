'use client'
import { useEffect, useRef } from 'react'
import type { Message } from '@/types/chat'
import UserMessage from './UserMessage'
import BotMessage from './BotMessage'

type MessageListProps = { messages: Message[] }

const MessageList = ({ messages }: MessageListProps) => {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    requestAnimationFrame(() => {
      if (ref.current) ref.current.scrollTop = ref.current.scrollHeight
    })
  }, [messages])

  return (
    <div
      ref={ref}
      style={{
        flex: 1,
        overflowY: 'auto',
        scrollbarWidth: 'thin',
      }}
    >
      <div
        style={{
          maxWidth: 760,
          margin: '0 auto',
          padding: '32px 28px 140px',
        }}
      >
        {messages.map((m) =>
          m.role === 'user'
            ? <UserMessage key={m.id} text={m.text} />
            : <BotMessage key={m.id} msg={m} />
        )}
      </div>
    </div>
  )
}

export default MessageList
