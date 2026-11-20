import { useState, type FormEvent } from 'react'

import { Button, FormField, Input } from '../../../components/ui'
import { toast } from '../../../store/toast.store'
import { billingApi } from '../api/billing.api'

export default function PasswordForm() {
  const [oldPassword, setOldPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)

    if (!oldPassword || !newPassword) {
      setError('Completa todos los campos.')
      return
    }
    if (newPassword.length < 8) {
      setError('La nueva contraseña debe tener al menos 8 caracteres.')
      return
    }
    if (newPassword !== confirmPassword) {
      setError('Las contraseñas nuevas no coinciden.')
      return
    }

    setLoading(true)
    try {
      await billingApi.changePassword({
        old_password: oldPassword,
        new_password: newPassword,
      })
      setOldPassword('')
      setNewPassword('')
      setConfirmPassword('')
      toast.success('Contraseña actualizada correctamente')
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        'No se pudo actualizar la contraseña.'
      setError(detail)
      toast.error('Error al cambiar contraseña', detail)
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="rounded-xl border border-border bg-card p-6">
      <div className="mb-4">
        <h2 className="text-base font-bold text-white">Seguridad</h2>
        <p className="mt-0.5 text-xs text-muted">Actualiza tu contraseña de acceso a MusicAI.</p>
      </div>

      <form onSubmit={handleSubmit} className="grid max-w-md gap-4">
        <FormField label="Contraseña actual" required>
          <Input
            type="password"
            value={oldPassword}
            onChange={(e) => setOldPassword(e.target.value)}
            disabled={loading}
            autoComplete="current-password"
          />
        </FormField>

        <FormField label="Nueva contraseña" hint="Mínimo 8 caracteres" required>
          <Input
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            disabled={loading}
            autoComplete="new-password"
          />
        </FormField>

        <FormField label="Confirmar nueva contraseña" required>
          <Input
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            disabled={loading}
            autoComplete="new-password"
          />
        </FormField>

        {error && (
          <p role="alert" className="text-xs text-error">
            {error}
          </p>
        )}

        <div>
          <Button type="submit" variant="secondary" loading={loading}>
            {loading ? 'Actualizando...' : 'Cambiar contraseña'}
          </Button>
        </div>
      </form>
    </section>
  )
}
