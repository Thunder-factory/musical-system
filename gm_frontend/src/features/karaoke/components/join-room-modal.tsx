import { useState, type ChangeEvent, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'

import { Button, FormField, Input, Modal } from '../../../components/ui'

interface JoinRoomModalProps {
  open: boolean
  onClose: () => void
}

export default function JoinRoomModal({ open, onClose }: JoinRoomModalProps) {
  const [code, setCode] = useState('')
  const [error, setError] = useState('')
  const navigate = useNavigate()

  function handleChange(e: ChangeEvent<HTMLInputElement>) {
    const val = e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 8)
    setCode(val)
    setError('')
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    const trimmed = code.trim().toUpperCase()
    if (trimmed.length !== 8) {
      setError('El código de sala tiene 8 caracteres.')
      return
    }
    onClose()
    navigate(`/karaoke/room/${trimmed}`)
  }

  return (
    <Modal open={open} onClose={onClose} title="Unirse a sala" size="sm">
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <p className="text-sm text-muted">
          Ingresa el código de 8 caracteres que te compartieron.
        </p>

        <FormField label="Código de sala" error={error || undefined} required>
          <Input
            value={code}
            onChange={handleChange}
            placeholder="AB12CD34"
            autoFocus
            maxLength={8}
            className="text-center text-xl font-bold uppercase tracking-[0.2em]"
          />
        </FormField>

        <div className="flex justify-end gap-2 pt-2">
          <Button variant="secondary" onClick={onClose}>
            Cancelar
          </Button>
          <Button type="submit" variant="primary" disabled={code.length !== 8}>
            Entrar a la sala
          </Button>
        </div>
      </form>
    </Modal>
  )
}
