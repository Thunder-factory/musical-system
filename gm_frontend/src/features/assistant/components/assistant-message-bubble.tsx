import { AlertCircle, RotateCcw } from 'lucide-react'
import { useLocation } from 'react-router-dom'

import { Button } from '../../../components/ui'
import { cn } from '../../../lib/cn'
import { useAssistantStore } from '../store/assistant.store'
import type { ChatMessage } from '../types/assistant.types'
import AssistantActions from './assistant-actions'
import AssistantMarkdown from './assistant-markdown'

interface AssistantMessageBubbleProps {
  message: ChatMessage
}

/** Burbuja individual: usuario a la derecha, asistente a la izquierda, errores en rojo suave. */
export default function AssistantMessageBubble({ message }: AssistantMessageBubbleProps) {
  const { pathname } = useLocation()
  const retry = useAssistantStore((s) => s.retry)
  const typing = useAssistantStore((s) => s.typing)
  const isUser = message.role === 'user'
  const isError = message.kind === 'error'

  return (
    <li className={cn('flex', isUser ? 'justify-end' : 'justify-start')}>
      <div
        className={cn(
          'max-w-[88%] rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed',
          isUser && 'rounded-br-md bg-primary text-black',
          !isUser && !isError && 'rounded-bl-md border border-border bg-card text-white/90',
          isError && 'rounded-bl-md border border-error-border bg-error-soft text-error'
        )}
      >
        <span className="sr-only">{isUser ? 'Tú: ' : 'Asistente: '}</span>
        {isUser ? (
          <p className="whitespace-pre-wrap break-words">{message.content}</p>
        ) : (
          <div className="flex gap-2">
            {isError && <AlertCircle size={16} className="mt-0.5 shrink-0" aria-hidden="true" />}
            <div className="min-w-0">
              <AssistantMarkdown text={message.content} />
              {message.actions && <AssistantActions actions={message.actions} />}
              {isError && message.retryable && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="-ml-2 mt-1"
                  disabled={typing}
                  leftIcon={<RotateCcw size={13} aria-hidden="true" />}
                  onClick={() => void retry(pathname)}
                >
                  Reintentar
                </Button>
              )}
            </div>
          </div>
        )}
      </div>
    </li>
  )
}
