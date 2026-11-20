import { SendHorizontal } from 'lucide-react'
import { useState, type FormEvent, type Ref } from 'react'
import { useLocation } from 'react-router-dom'

import { Button } from '../../../components/ui'
import { MAX_CONTENT } from '../lib/build-history'
import { useAssistantStore } from '../store/assistant.store'

interface AssistantInputProps {
  inputRef: Ref<HTMLInputElement>
}

/** Campo de pregunta con botón de enviar (deshabilitado mientras responde). */
export default function AssistantInput({ inputRef }: AssistantInputProps) {
  const { pathname } = useLocation()
  const send = useAssistantStore((s) => s.send)
  const typing = useAssistantStore((s) => s.typing)
  const [text, setText] = useState('')
  const canSend = text.trim().length > 0 && !typing

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!canSend) {
      return
    }
    void send(text, pathname)
    setText('')
  }

  return (
    <form onSubmit={handleSubmit} className="flex items-center gap-2 border-t border-border p-3">
      <label htmlFor="assistant-input" className="sr-only">
        Escribe tu pregunta
      </label>
      <input
        id="assistant-input"
        ref={inputRef}
        value={text}
        onChange={(event) => setText(event.target.value)}
        maxLength={MAX_CONTENT}
        autoComplete="off"
        placeholder="Pregúntame lo que quieras…"
        className="h-10 min-w-0 flex-1 rounded-lg border border-border-strong bg-card px-3 text-sm text-white placeholder:text-muted focus:border-primary"
      />
      <Button
        type="submit"
        size="md"
        disabled={!canSend}
        loading={typing}
        aria-label="Enviar pregunta"
        className="w-10 px-0"
        leftIcon={typing ? undefined : <SendHorizontal size={16} aria-hidden="true" />}
      />
    </form>
  )
}
