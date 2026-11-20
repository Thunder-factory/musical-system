import { Shield, ShieldOff, UserCheck, UserX } from 'lucide-react'

import { Badge, Button } from '../../../components/ui'
import type { AdminUser } from '../api/admin.api'

interface UserRowProps {
  user: AdminUser
  isSelf: boolean
  busy: boolean
  onToggleRole: (user: AdminUser) => void
  onToggleActive: (user: AdminUser) => void
}

export default function UserRow({
  user,
  isSelf,
  busy,
  onToggleRole,
  onToggleActive,
}: UserRowProps) {
  const initials = user.full_name
    ? user.full_name
        .split(' ')
        .map((n) => n[0])
        .join('')
        .slice(0, 2)
        .toUpperCase()
    : '?'

  return (
    <tr className="border-t border-border transition-colors hover:bg-card-hover/60">
      <td className="px-3 py-2.5">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[var(--gradient-primary)] text-xs font-bold text-black">
            {initials}
          </div>
          <div className="min-w-0 max-w-[200px]">
            <p className="truncate text-sm font-medium text-white">
              {user.full_name || '—'}
              {isSelf && <span className="ml-1.5 text-xs text-primary">(Tú)</span>}
            </p>
            <p className="truncate text-xs text-muted">{user.email}</p>
          </div>
        </div>
      </td>

      <td className="whitespace-nowrap px-2.5 py-2.5 text-xs text-muted">{user.plan_name || 'Free'}</td>

      <td className="whitespace-nowrap px-2.5 py-2.5 text-sm font-semibold tabular-nums text-primary">
        {user.credit_balance}
      </td>

      <td className="whitespace-nowrap px-2.5 py-2.5">
        <Badge variant={user.is_staff ? 'primary' : 'success'}>
          {user.is_staff ? 'Admin' : 'Cliente'}
        </Badge>
      </td>

      <td className="whitespace-nowrap px-2.5 py-2.5">
        <Badge variant={user.is_active ? 'success' : 'error'}>
          {user.is_active ? 'Activo' : 'Inactivo'}
        </Badge>
      </td>

      <td className="whitespace-nowrap px-2.5 py-2.5 text-xs text-muted">
        {new Date(user.created_at).toLocaleDateString('es-ES', {
          day: '2-digit',
          month: 'short',
          year: 'numeric',
        })}
      </td>

      <td className="whitespace-nowrap px-3 py-2.5">
        <div className="flex justify-end gap-1.5">
          <Button
            variant="secondary"
            size="sm"
            disabled={isSelf || busy}
            title={
              isSelf
                ? 'No puedes cambiar tu propio rol'
                : user.is_staff
                  ? 'Cambiar a cliente'
                  : 'Promover a administrador'
            }
            leftIcon={user.is_staff ? <ShieldOff size={13} /> : <Shield size={13} />}
            onClick={() => onToggleRole(user)}
          >
            {user.is_staff ? 'Quitar admin' : 'Hacer admin'}
          </Button>

          <Button
            variant={user.is_active ? 'danger' : 'secondary'}
            size="sm"
            disabled={isSelf || busy}
            title={
              isSelf
                ? 'No puedes desactivar tu propia cuenta'
                : user.is_active
                  ? 'Desactivar cuenta'
                  : 'Activar cuenta'
            }
            leftIcon={user.is_active ? <UserX size={13} /> : <UserCheck size={13} />}
            onClick={() => onToggleActive(user)}
          >
            {user.is_active ? 'Desactivar' : 'Activar'}
          </Button>
        </div>
      </td>
    </tr>
  )
}
