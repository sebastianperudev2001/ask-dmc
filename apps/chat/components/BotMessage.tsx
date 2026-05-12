import type { BotMsg } from '@/types/chat'
import BotAvatar from './BotAvatar'
import ThinkingBlock from './ThinkingBlock'
import ToolCallBlock from './ToolCallBlock'
import SourceChips from './SourceChips'

type BotMessageProps = { msg: BotMsg }

const BotMessage = ({ msg }: BotMessageProps) => {
  const isThinking = msg.phase === 'searching' || msg.phase === 'streaming'
  const toolStatus = msg.phase === 'searching' ? 'running' : 'done'

  return (
    <div
      style={{
        display: 'flex',
        gap: 14,
        marginBottom: 24,
        alignItems: 'flex-start',
      }}
    >
      <div style={{ flexShrink: 0, marginTop: 2 }}>
        <BotAvatar size={32} state={isThinking ? 'thinking' : 'idle'} />
      </div>
      <div style={{ flex: 1, minWidth: 0, fontSize: 14.5, lineHeight: 1.6 }}>
        <ToolCallBlock
          name="search_brochures"
          args={`{ "question": "${msg.question}" }`}
          result={
            msg.sources.length
              ? msg.sources.map((s) => `→ ${s.course} / ${s.section}`).join('\n')
              : null
          }
          status={toolStatus}
        />
        {(msg.answer || msg.phase === 'streaming') && (
          <div style={{ whiteSpace: 'pre-wrap', color: 'var(--color-text)' }}>
            {msg.answer}
            {!msg.answerDone && <span className="cursor" />}
          </div>
        )}
        {msg.answerDone && <SourceChips sources={msg.sources} />}
      </div>
    </div>
  )
}

export default BotMessage
