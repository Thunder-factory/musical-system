import { useEffect, useRef, useState } from 'react'

import { authService } from '../../../api/auth-service'
import { Badge, Button, FormField, Input } from '../../../components/ui'
import { useAuthStore } from '../../../store/auth.store'
import { toast } from '../../../store/toast.store'

export default function AdminProfilePage() {
  const { user, setUser } = useAuthStore()
  const fileRef = useRef<HTMLInputElement>(null)

  const [editing, setEditing] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [form, setForm] = useState({
    full_name: user?.full_name ?? '',
    avatar_url: user?.avatar_url ?? '',
  })

  useEffect(() => {
    if (!editing) {
      setForm({
        full_name: user?.full_name ?? '',
        avatar_url: user?.avatar_url ?? '',
      })
    }
  }, [editing, user?.avatar_url, user?.full_name])

  function handleImageChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) {
      return
    }
    const reader = new FileReader()
    reader.onload = () => setForm((f) => ({ ...f, avatar_url: String(reader.result ?? '') }))
    reader.readAsDataURL(file)
  }

  async function handleSave() {
    if (!user) {
      return
    }
    setLoading(true)
    setError(null)
    try {
      const payload: { full_name?: string; avatar_url?: string } = {}
      if (form.full_name !== user.full_name) {
        payload.full_name = form.full_name
      }
      if (form.avatar_url !== (user.avatar_url ?? '')) {
        payload.avatar_url = form.avatar_url
      }
      await authService.updateProfile(payload)
      setUser(await authService.getProfile())
      setEditing(false)
      toast.success('Perfil actualizado correctamente')
    } catch (e: unknown) {
      const msg =
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        'Error al guardar los cambios.'
      setError(msg)
      toast.error('No se pudo guardar el perfil', msg)
    } finally {
      setLoading(false)
    }
  }

  const initials = user?.full_name
    ? user.full_name
        .split(' ')
        .map((n) => n[0])
        .join('')
        .slice(0, 2)
        .toUpperCase()
    : '?'
  const joinDate = user?.created_at
    ? new Date(user.created_at).toLocaleDateString('es-ES', { month: 'long', year: 'numeric' })
    : null

  return (
    <div className="max-w-2xl space-y-6 p-6 text-white">
      <header>
        <h1 className="text-2xl font-black tracking-tight">Mi perfil</h1>
        {joinDate && <p className="mt-0.5 text-xs text-muted">Miembro desde {joinDate}</p>}
      </header>

      <div className="space-y-6 rounded-xl border border-border bg-card p-6">
        <div className="flex items-center gap-5">
          {form.avatar_url ? (
            <img
              src={form.avatar_url}
              alt="Avatar"
              className="h-20 w-20 rounded-full border-2 border-primary object-cover"
            />
          ) : (
            <div className="flex h-20 w-20 select-none items-center justify-center rounded-full bg-[var(--gradient-primary)] text-2xl font-black text-black">
              {initials}
            </div>
          )}

          {editing && (
            <div>
              <Button variant="secondary" size="sm" onClick={() => fileRef.current?.click()}>
                Cambiar foto
              </Button>
              <input
                ref={fileRef}
                type="file"
                accept="image/*"
                className="sr-only"
                onChange={handleImageChange}
              />
            </div>
          )}
        </div>

        <div className="space-y-4">
          {editing ? (
            <FormField label="Nombre completo" required>
              <Input
                name="full_name"
                value={form.full_name}
                onChange={(e) => setForm((f) => ({ ...f, full_name: e.target.value }))}
                disabled={loading}
              />
            </FormField>
          ) : (
            <div>
              <p className="text-xs font-semibold text-muted">Nombre completo</p>
              <p className="mt-1 text-sm font-medium text-white">{user?.full_name ?? '—'}</p>
            </div>
          )}

          <div>
            <p className="text-xs font-semibold text-muted">Correo electrónico</p>
            <p className="mt-1 text-sm font-medium text-white">{user?.email ?? '—'}</p>
            <p className="mt-0.5 text-xs text-muted">
              El correo electrónico no se puede modificar desde el panel.
            </p>
          </div>

          <div>
            <p className="mb-1 text-xs font-semibold text-muted">Rol</p>
            <Badge variant="primary">{user?.role ?? 'admin'}</Badge>
          </div>
        </div>

        {error && <p className="text-xs text-error">{error}</p>}

        <div className="flex gap-3">
          {editing ? (
            <>
              <Button variant="primary" loading={loading} onClick={() => void handleSave()}>
                {loading ? 'Guardando...' : 'Guardar cambios'}
              </Button>
              <Button
                variant="secondary"
                disabled={loading}
                onClick={() => {
                  setForm({ full_name: user?.full_name ?? '', avatar_url: user?.avatar_url ?? '' })
                  setEditing(false)
                  setError(null)
                }}
              >
                Cancelar
              </Button>
            </>
          ) : (
            <Button variant="primary" onClick={() => setEditing(true)}>
              Editar perfil
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}
