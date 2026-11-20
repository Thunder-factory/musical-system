import { useEffect, useState } from 'react'
import { ArrowRight, Shield, Users } from 'lucide-react'
import { Link } from 'react-router-dom'

import { Badge } from '../../../components/ui'
import { toast } from '../../../store/toast.store'
import { adminApi, type AdminUser } from '../api/admin.api'

export default function RolesPage() {
  const [users, setUsers] = useState<AdminUser[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    adminApi
      .getAdminUsers()
      .then(setUsers)
      .catch(() => toast.error('No se pudo cargar el resumen de roles'))
      .finally(() => setLoading(false))
  }, [])

  const adminCount = users.filter((u) => u.is_staff || u.role === 'admin').length
  const clientCount = users.length - adminCount

  const roles = [
    {
      name: 'admin',
      label: 'Administrador',
      description: 'Acceso completo al panel administrativo, usuarios, planes y métricas.',
      count: adminCount,
      variant: 'primary' as const,
    },
    {
      name: 'user',
      label: 'Cliente',
      description: 'Cuenta estándar con acceso al estudio musical, comunidad y biblioteca.',
      count: clientCount,
      variant: 'success' as const,
    },
  ]

  return (
    <div className="space-y-6 p-6 text-white">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Roles del sistema</h1>
          <p className="mt-1 text-sm text-muted">
            Resumen actual de permisos asignados en la plataforma.
          </p>
        </div>

        <Link
          to="/admin/usuarios"
          className="inline-flex h-10 items-center gap-2 rounded-lg bg-primary px-4 text-sm font-semibold text-black transition-colors hover:bg-primary-hover"
        >
          Gestionar roles en Usuarios
          <ArrowRight size={15} aria-hidden="true" />
        </Link>
      </header>

      <div className="grid gap-4 sm:grid-cols-2">
        {roles.map((r) => (
          <div
            key={r.name}
            className="flex items-center justify-between rounded-xl border border-border bg-card p-5"
          >
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-muted">
                {r.label}
              </p>
              <p className="mt-1.5 text-3xl font-black tabular-nums text-white">
                {loading ? '…' : r.count.toLocaleString('es-ES')}
              </p>
              <p className="mt-1 text-xs text-muted">cuentas activas o registradas</p>
            </div>
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary-soft text-primary">
              {r.name === 'admin' ? (
                <Shield size={18} aria-hidden="true" />
              ) : (
                <Users size={18} aria-hidden="true" />
              )}
            </div>
          </div>
        ))}
      </div>

      <div className="overflow-x-auto rounded-xl border border-border bg-card">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-card-hover text-xs uppercase tracking-wider text-muted">
              <th className="px-4 py-3 text-left">Rol</th>
              <th className="px-4 py-3 text-left">Descripción</th>
              <th className="px-4 py-3 text-left">Usuarios</th>
              <th className="px-4 py-3 text-left">Tipo</th>
            </tr>
          </thead>
          <tbody>
            {roles.map((role, i) => (
              <tr key={role.name} className={i % 2 === 0 ? 'bg-surface' : 'bg-night'}>
                <td className="px-4 py-3 font-mono text-sm font-bold text-primary">
                  {role.name}
                </td>
                <td className="px-4 py-3 text-sm text-muted">{role.description}</td>
                <td className="px-4 py-3 font-semibold tabular-nums text-white">
                  {loading ? '…' : role.count.toLocaleString('es-ES')}
                </td>
                <td className="px-4 py-3">
                  <Badge variant={role.variant}>Sistema</Badge>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="text-xs text-muted">
        Para promover o degradar una cuenta, entra a{' '}
        <Link to="/admin/usuarios" className="font-semibold text-primary hover:underline">
          Usuarios
        </Link>{' '}
        y usa la acción correspondiente en la fila del usuario.
      </p>
    </div>
  )
}
