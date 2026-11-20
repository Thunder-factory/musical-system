import { useEffect, useRef, useState } from 'react'

import { authService } from '../../../api/auth-service'
import { Badge, Button, FormField, Input } from '../../../components/ui'
import { useAuthStore } from '../../../store/auth.store'
import { toast } from '../../../store/toast.store'

export default function ProfileInfoForm() {
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
    setLoading(true)
    setError(null)
    try {
      const payload: { full_name?: string; avatar_url?: string } = {}
      if (form.full_name !== user?.full_name) {
        payload.full_name = form.full_name
      }
      if (form.avatar_url !== (user?.avatar_url ?? '')) {
        payload.avatar_url = form.avatar_url
      }
      await authService.updateProfile(payload)
      setUser(await authService.getProfile())
      setEditing(false)
      toast.success('Perfil actualizado')
    } catch (e: unknown) {
      const msg =
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        'No se pudo actualizar tu perfil.'
      setError(msg)
      toast.error('Error al guardar perfil', msg)
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
    : '—'
  const roleLabel = user?.role === 'admin' ? 'Administrador' : 'Cliente'

  return (
    <section className="rounded-xl border border-border bg-card p-6">
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div className="flex min-w-0 items-center gap-4">
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
          <div className="min-w-0">
            <h2 className="truncate text-lg font-bold text-white">
              {user?.full_name ?? 'Sin nombre'}
            </h2>
            <p className="mt-0.5 truncate text-sm text-muted">{user?.email ?? '—'}</p>
            <div className="mt-2">
              <Badge variant="primary">Cuenta {roleLabel.toLowerCase()}</Badge>
            </div>
          </div>
        </div>

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

      <div className="mb-5 grid gap-3 border-y border-border py-4 sm:grid-cols-3">
        <div className="rounded-lg bg-card-hover px-4 py-3">
          <p className="text-[10px] font-bold uppercase tracking-wider text-muted">Créditos</p>
          <p className="mt-1 text-xl font-black tabular-nums text-primary">
            {user?.credit_balance ?? 0}
          </p>
        </div>
        <div className="rounded-lg bg-card-hover px-4 py-3">
          <p className="text-[10px] font-bold uppercase tracking-wider text-muted">Rol</p>
          <p className="mt-1 text-sm font-bold text-white">{roleLabel}</p>
        </div>
        <div className="rounded-lg bg-card-hover px-4 py-3">
          <p className="text-[10px] font-bold uppercase tracking-wider text-muted">Miembro desde</p>
          <p className="mt-1 text-sm font-bold capitalize text-white">{joinDate}</p>
        </div>
      </div>

      <div className="flex flex-col gap-4">
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
        </div>
      </div>

      {error && <p className="mt-4 text-xs text-error">{error}</p>}

      <div className="mt-6 flex gap-3">
        {editing ? (
          <>
            <Button variant="primary" loading={loading} onClick={() => void handleSave()}>
              {loading ? 'Guardando...' : 'Guardar'}
            </Button>
            <Button
              variant="secondary"
              disabled={loading}
              onClick={() => {
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
    </section>
  )
}
