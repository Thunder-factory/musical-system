import { useEffect, useRef } from 'react'

import { useAssistantStore } from '../store/assistant.store'
import AssistantMessageBubble from './assistant-message-bubble'
import AssistantWelcome from './assistant-welcome'

/** Lista de mensajes con saludo inicial, indicador "escribiendo…" y autoscroll. */
export default function AssistantMessageList() {
  const messages = useAssistantStore((s) => s.messages)
  const typing = useAssistantStore((s) => s.typing)
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'end' })
  }, [messages.length, typing])

  return (
    <div className="min-h-0 flex-1 overflow-y-auto px-3 py-3">
      <ul className="flex flex-col gap-2.5" aria-live="polite" aria-relevant="additions">
        <AssistantWelcome />
        {messages.map((message) => (
          <AssistantMessageBubble key={message.id} message={message} />
        ))}
        {typing && (
          <li className="flex justify-start">
            <div className="inline-flex items-center gap-2 rounded-2xl rounded-bl-md border border-border bg-card px-3.5 py-2.5 text-sm text-muted">
              <span className="flex gap-1" aria-hidden="true">
                <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-primary [animation-delay:-0.3s]" />
                <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-primary [animation-delay:-0.15s]" />
                <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-primary" />
              </span>
              escribiendo…
            </div>
          </li>
        )}
      </ul>
      <div ref={endRef} />
    </div>
  )
}
