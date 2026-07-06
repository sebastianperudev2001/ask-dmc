import ReactMarkdown from 'react-markdown'
import type { BotMsg, ProfileData } from '@/types/chat'
import BotAvatar from './BotAvatar'
import ToolCallBlock from './ToolCallBlock'
import ProfileDataWidget from './ProfileDataWidget'
import CourseRecommendationCard from './CourseRecommendationCard'
import PaymentLinkButton from './PaymentLinkButton'

type BotMessageProps = {
  msg: BotMsg
  onSubmitProfileData: (callId: string, data: ProfileData) => void
}

const BotMessage = ({ msg, onSubmitProfileData }: BotMessageProps) => {
  const isThinking = msg.phase === 'streaming' && !msg.answer

  // The agent writes the checkout URL inline in its own prose (system prompt
  // instructs it to share the link in chat) — strip it here since PaymentLinkButton
  // below already renders it as a proper button; keeping both duplicates an ugly
  // raw URL right next to the styled button.
  const displayAnswer = msg.toolCalls.reduce(
    (text, toolCall) =>
      toolCall.name === 'create_payment_link' && toolCall.resultText
        ? text.split(toolCall.resultText).join('')
        : text,
    msg.answer
  )

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
        {(msg.answer || msg.phase !== 'done') && (
          <div className="prose">
            <ReactMarkdown>{displayAnswer}</ReactMarkdown>
            {!msg.answerDone && <span className="cursor" />}
          </div>
        )}

        {msg.profileRequest && (
          <ProfileDataWidget
            callId={msg.profileRequest.callId}
            prefill={msg.profileRequest.prefill}
            onSubmit={onSubmitProfileData}
          />
        )}

        <CourseRecommendationCard recommendations={msg.recommendations} />

        {msg.toolCalls.map((toolCall, idx) =>
          toolCall.name === 'create_payment_link' && toolCall.status === 'done' && toolCall.resultText ? (
            <PaymentLinkButton key={`${toolCall.name}-${idx}`} checkoutUrl={toolCall.resultText} />
          ) : (
            <ToolCallBlock
              key={`${toolCall.name}-${idx}`}
              name={toolCall.name}
              args={toolCall.argsText}
              result={toolCall.resultText}
              status={toolCall.status}
            />
          )
        )}
      </div>
    </div>
  )
}

export default BotMessage
