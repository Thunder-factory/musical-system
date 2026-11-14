import { useEffect, useState } from 'react'
import client from '../../api/client'
import { ENDPOINTS } from '../../api/endpoints'

interface AdminUser {
  id: string
  full_name: string
  email: string
  credit_balance: number
  is_active: boolean
  is_staff: boolean
  created_at: string
}

export default function UsersAdminPage() {
  const [users, setUsers] = useState<AdminUser[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [query, setQuery] = useState('')

  useEffect(() => {
    setLoading(true)
    const url = query
      ? `${ENDPOINTS.reports.users}?search=${encodeURIComponent(query)}`
      : ENDPOINTS.reports.users
    client
      .get<AdminUser[]>(url)
      .then(({ data }) => setUsers(data))
      .catch(() => setError('No se pudo cargar la lista de usuarios.'))
      .finally(() => setLoading(false))
  }, [query])

  function handleSearch(e: React.FormEvent) {
    e.preventDefault()
    setQuery(search.trim())
  }

  return (
    <div style={{ minHeight: '100%', padding: '28px 32px', color: 'var(--text-base)' }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 24,
        }}
      >
        <div>
          <h1 style={{ fontSize: 28, fontWeight: 700, margin: 0, letterSpacing: '-0.02em' }}>
            Usuarios
          </h1>
          <p style={{ fontSize: 14, color: 'var(--text-subdued)', margin: '4px 0 0' }}>
            {loading ? '...' : `${users.length} usuario${users.length !== 1 ? 's' : ''}`}
          </p>
        </div>
      </div>

      {error && (
        <div
          style={{
            background: 'var(--color-error-soft)',
            border: '1px solid var(--color-error-border)',
            color: 'var(--color-error)',
            borderRadius: 8,
            padding: '12px 16px',
            fontSize: 14,
            marginBottom: 20,
          }}
        >
          {error}
        </div>
      )}

      {/* Search */}
      <form onSubmit={handleSearch} style={{ display: 'flex', gap: 10, marginBottom: 20 }}>
        <div style={{ position: 'relative', flex: 1, maxWidth: 400 }}>
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="currentColor"
            style={{
              position: 'absolute',
              left: 14,
              top: '50%',
              transform: 'translateY(-50%)',
              color: 'var(--text-subdued)',
              pointerEvents: 'none',
            }}
          >
            <path d="M15.5 14h-.79l-.28-.27A6.471 6.471 0 0016 9.5 6.5 6.5 0 109.5 16a6.471 6.471 0 004.23-1.57l.27.28v.79L20 21.5 21.5 20l-6-6zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z" />
          </svg>
          <input
            type="text"
            placeholder="Buscar por nombre o email..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{
              width: '100%',
              background: 'var(--bg-card-hover)',
              border: '1px solid transparent',
              borderRadius: 4,
              padding: '10px 14px 10px 40px',
              fontSize: 14,
              color: 'var(--text-base)',
              outline: 'none',
              boxSizing: 'border-box',
            }}
            onFocus={(e) => (e.target.style.borderColor = 'var(--color-primary)')}
            onBlur={(e) => (e.target.style.borderColor = 'transparent')}
          />
        </div>
        <button
          type="submit"
          style={{
            padding: '10px 18px',
            borderRadius: 4,
            fontSize: 13,
            fontWeight: 600,
            background: 'var(--bg-card-hover)',
            color: 'var(--text-base)',
            border: '1px solid var(--border)',
            cursor: 'pointer',
          }}
        >
          Buscar
        </button>
        {query && (
          <button
            type="button"
            onClick={() => {
              setSearch('')
              setQuery('')
            }}
            style={{
              padding: '10px 14px',
              borderRadius: 4,
              fontSize: 13,
              background: 'none',
              color: 'var(--text-subdued)',
              border: '1px solid var(--border)',
              cursor: 'pointer',
            }}
          >
            Limpiar
          </button>
        )}
      </form>

      {/* Table */}
      <div
        style={{
          background: 'var(--bg-card)',
          borderRadius: 8,
          border: '1px solid var(--border)',
          overflow: 'hidden',
        }}
      >
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ background: 'var(--bg-card-hover)' }}>
              {['Nombre', 'Email', 'Créditos', 'Rol', 'Estado', 'Registro'].map((h) => (
                <th
                  key={h}
                  style={{
                    padding: '12px 16px',
                    textAlign: 'left',
                    fontSize: 12,
                    fontWeight: 600,
                    color: 'var(--text-subdued)',
                    textTransform: 'uppercase',
                    letterSpacing: '0.06em',
                  }}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              Array.from({ length: 8 }).map((_, i) => (
                <tr key={i}>
                  {Array.from({ length: 6 }).map((_, j) => (
                    <td key={j} style={{ padding: '14px 16px' }}>
                      <div
                        style={{
                          height: 14,
                          borderRadius: 4,
                          background: 'var(--gradient-skeleton)',
                          backgroundSize: '200% 100%',
                          animation: 'shimmer 1.5s infinite',
                          width: j === 1 ? '80%' : '60%',
                        }}
                      />
                    </td>
                  ))}
                </tr>
              ))
            ) : users.length === 0 ? (
              <tr>
                <td
                  colSpan={6}
                  style={{
                    padding: '40px',
                    textAlign: 'center',
                    color: 'var(--text-subdued)',
                    fontSize: 14,
                  }}
                >
                  No se encontraron usuarios.
                </td>
              </tr>
            ) : (
              users.map((u) => (
                <tr
                  key={u.id}
                  style={{ borderTop: '1px solid var(--border)' }}
                  onMouseEnter={(e) =>
                    ((e.currentTarget as HTMLTableRowElement).style.background =
                      'var(--bg-card-hover)')
                  }
                  onMouseLeave={(e) =>
                    ((e.currentTarget as HTMLTableRowElement).style.background = 'transparent')
                  }
                >
                  <td style={{ padding: '12px 16px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <div
                        style={{
                          width: 32,
                          height: 32,
                          borderRadius: '50%',
                          flexShrink: 0,
                          background: 'var(--gradient-primary)',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          fontSize: 12,
                          fontWeight: 700,
                          color: 'var(--text-base)',
                        }}
                      >
                        {u.full_name
                          ? u.full_name
                              .split(' ')
                              .map((n) => n[0])
                              .join('')
                              .slice(0, 2)
                              .toUpperCase()
                          : '?'}
                      </div>
                      <span style={{ fontSize: 14, fontWeight: 500 }}>{u.full_name || '—'}</span>
                    </div>
                  </td>
                  <td style={{ padding: '12px 16px', fontSize: 14, color: 'var(--text-subdued)' }}>
                    {u.email}
                  </td>
                  <td style={{ padding: '12px 16px' }}>
                    <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--color-primary)' }}>
                      {u.credit_balance}
                    </span>
                  </td>
                  <td style={{ padding: '12px 16px' }}>
                    <span
                      style={{
                        fontSize: 12,
                        fontWeight: 600,
                        padding: '3px 10px',
                        borderRadius: 500,
                        background: u.is_staff ? 'var(--color-primary-subtle)' : 'var(--color-success-soft)',
                        color: u.is_staff ? 'var(--color-primary)' : 'var(--color-success)',
                      }}
                    >
                      {u.is_staff ? 'Admin' : 'Usuario'}
                    </span>
                  </td>
                  <td style={{ padding: '12px 16px' }}>
                    <span
                      style={{
                        fontSize: 12,
                        fontWeight: 500,
                        padding: '3px 10px',
                        borderRadius: 500,
                        background: u.is_active ? 'var(--color-success-soft)' : 'var(--color-error-soft)',
                        color: u.is_active ? 'var(--color-success)' : 'var(--color-error)',
                      }}
                    >
                      {u.is_active ? 'Activo' : 'Inactivo'}
                    </span>
                  </td>
                  <td style={{ padding: '12px 16px', fontSize: 13, color: 'var(--text-subdued)' }}>
                    {new Date(u.created_at).toLocaleDateString('es-ES', {
                      day: '2-digit',
                      month: 'short',
                      year: 'numeric',
                    })}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <style>{`@keyframes shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }`}</style>
    </div>
  )
}
