import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Search, Users } from 'lucide-react'

import { Button, EmptyState, Input, useConfirm } from '../../../components/ui'
import { useAuthStore } from '../../../store/auth.store'
import { toast } from '../../../store/toast.store'
import { adminApi, type AdminUser } from '../api/admin.api'
import UserRow from '../components/user-row'

export default function UsersAdminPage() {
  const currentUserId = useAuthStore((s) => s.user?.id)
  const confirm = useConfirm()

  const [users, setUsers] = useState<AdminUser[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [query, setQuery] = useState('')
  const [busyUserId, setBusyUserId] = useState<string | null>(null)

  const fetchUsers = useCallback(async (q: string) => {
    setLoading(true)
    setError(null)
    try {
      setUsers(await adminApi.getAdminUsers(q))
    } catch {
      setError('No se pudo cargar la lista de usuarios.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void fetchUsers(query)
  }, [fetchUsers, query])

  function handleSearch(e: FormEvent) {
    e.preventDefault()
    setQuery(search.trim())
  }

  async function handleToggleRole(target: AdminUser) {
    if (target.id === currentUserId) {
      return
    }
    const makeAdmin = !target.is_staff
    const accepted = await confirm({
      title: makeAdmin ? 'Promover a administrador' : 'Cambiar a cliente',
      description: makeAdmin
        ? `¿Quieres otorgar permisos de administrador a ${target.full_name || target.email}?`
        : `¿Quieres quitar el rol de administrador a ${target.full_name || target.email}?`,
      confirmLabel: makeAdmin ? 'Hacer admin' : 'Quitar admin',
      variant: makeAdmin ? 'primary' : 'danger',
    })
    if (!accepted) {
      return
    }

    setBusyUserId(target.id)
    try {
      const updated = await adminApi.updateAdminUser(target.id, { is_staff: makeAdmin })
      setUsers((prev) => prev.map((u) => (u.id === updated.id ? updated : u)))
      toast.success('Rol actualizado', `${updated.email} ahora es ${updated.is_staff ? 'Admin' : 'Cliente'}.`)
    } catch {
      toast.error('No se pudo actualizar el rol del usuario')
    } finally {
      setBusyUserId(null)
    }
  }

  async function handleToggleActive(target: AdminUser) {
    if (target.id === currentUserId) {
      return
    }
    const nextActive = !target.is_active
    const accepted = await confirm({
      title: nextActive ? 'Activar cuenta' : 'Desactivar cuenta',
      description: nextActive
        ? `¿Deseas reactivar el acceso de ${target.full_name || target.email}?`
        : `¿Deseas desactivar la cuenta de ${target.full_name || target.email}? No podrá iniciar sesión.`,
      confirmLabel: nextActive ? 'Activar' : 'Desactivar',
      variant: nextActive ? 'primary' : 'danger',
    })
    if (!accepted) {
      return
    }

    setBusyUserId(target.id)
    try {
      const updated = await adminApi.updateAdminUser(target.id, { is_active: nextActive })
      setUsers((prev) => prev.map((u) => (u.id === updated.id ? updated : u)))
      toast.success(
        nextActive ? 'Cuenta activada' : 'Cuenta desactivada',
        updated.email
      )
    } catch {
      toast.error('No se pudo cambiar el estado de la cuenta')
    } finally {
      setBusyUserId(null)
    }
  }

  return (
    <div className="space-y-5 p-6 text-white">
      <header>
        <h1 className="text-2xl font-bold tracking-tight">Usuarios</h1>
        <p className="mt-1 text-sm text-muted">
          {loading ? 'Cargando...' : `${users.length} usuario${users.length !== 1 ? 's' : ''}`}
        </p>
      </header>

      {error && (
        <div
          role="alert"
          className="rounded-xl border border-error-border bg-error-soft px-4 py-3 text-sm text-error"
        >
          {error}
        </div>
      )}

      <form onSubmit={handleSearch} className="flex flex-wrap items-center gap-2.5">
        <div className="relative min-w-[240px] max-w-md flex-1">
          <Search
            size={15}
            aria-hidden="true"
            className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-muted"
          />
          <Input
            type="text"
            placeholder="Buscar por nombre o email..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            aria-label="Buscar usuarios"
            className="pl-10"
          />
        </div>
        <Button type="submit" variant="secondary">
          Buscar
        </Button>
        {query && (
          <Button
            variant="ghost"
            onClick={() => {
              setSearch('')
              setQuery('')
            }}
          >
            Limpiar
          </Button>
        )}
      </form>

      <div className="overflow-x-auto rounded-xl border border-border bg-card">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="bg-card-hover text-xs font-semibold uppercase tracking-wider text-muted">
              <th className="px-3 py-3 text-left">Usuario</th>
              <th className="px-2.5 py-3 text-left">Plan</th>
              <th className="px-2.5 py-3 text-left">Créditos</th>
              <th className="px-2.5 py-3 text-left">Rol</th>
              <th className="px-2.5 py-3 text-left">Estado</th>
              <th className="px-2.5 py-3 text-left">Registro</th>
              <th className="px-3 py-3 text-right">Acciones</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              Array.from({ length: 6 }).map((_, i) => (
                <tr key={i} className="border-t border-border">
                  <td colSpan={7} className="px-4 py-3.5">
                    <div className="h-4 animate-pulse rounded bg-card-hover" />
                  </td>
                </tr>
              ))
            ) : users.length === 0 ? (
              <tr>
                <td colSpan={7} className="p-6">
                  <EmptyState
                    icon={<Users size={22} />}
                    title="No se encontraron usuarios"
                    description={
                      query
                        ? 'Prueba con otro nombre o correo electrónico.'
                        : 'Aún no hay usuarios registrados.'
                    }
                  />
                </td>
              </tr>
            ) : (
              users.map((u) => (
                <UserRow
                  key={u.id}
                  user={u}
                  isSelf={u.id === currentUserId}
                  busy={busyUserId === u.id}
                  onToggleRole={(user) => void handleToggleRole(user)}
                  onToggleActive={(user) => void handleToggleActive(user)}
                />
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
