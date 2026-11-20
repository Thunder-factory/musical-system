import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowLeft, Eye, EyeOff } from 'lucide-react'

import { Button, FormField, Input } from '../../../components/ui'
import { useAuthStore } from '../../../store/auth.store'
import { formatAuthError, getMeRequest, loginRequest } from '../api/auth.api'

export default function LoginPage() {
  const navigate = useNavigate()
  const setTokens = useAuthStore((s) => s.setTokens)
  const setUser = useAuthStore((s) => s.setUser)

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    setLoading(true)
    try {
      const tokens = await loginRequest(email.trim(), password)
      setTokens(tokens.access, tokens.refresh)
      const me = await getMeRequest()
      setUser(me)
      navigate(me.role === 'admin' ? '/admin' : '/inicio', { replace: true })
    } catch (err: unknown) {
      setError(formatAuthError(err, 'Credenciales incorrectas.'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="w-full max-w-[400px] rounded-2xl border border-border bg-surface/90 p-6 sm:p-8 shadow-[var(--shadow)]">
      <div className="text-center">
        <img src="/logo.png" alt="MusicAI" className="mx-auto mb-4 h-16 w-16 object-contain" />
        <h1 className="text-2xl font-bold tracking-tight text-white">¡Hola de nuevo!</h1>
        <p className="mt-1.5 text-sm text-muted">Ingresa a MusicAI para continuar.</p>
      </div>

      <form onSubmit={handleSubmit} className="mt-6 flex flex-col gap-4">
        <FormField label="Correo electrónico" required>
          <Input
            type="email"
            placeholder="tu@email.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoComplete="email"
            disabled={loading}
          />
        </FormField>

        <FormField label="Contraseña" required>
          <div className="relative">
            <Input
              type={showPassword ? 'text' : 'password'}
              placeholder="Ingresa tu contraseña"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
              disabled={loading}
              className="pr-10"
            />
            <button
              type="button"
              onClick={() => setShowPassword((prev) => !prev)}
              aria-label={showPassword ? 'Ocultar contraseña' : 'Mostrar contraseña'}
              className="absolute right-2.5 top-1/2 flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded-md text-muted transition-colors hover:text-white"
            >
              {showPassword ? <EyeOff size={16} aria-hidden="true" /> : <Eye size={16} aria-hidden="true" />}
            </button>
          </div>
        </FormField>

        {error && (
          <p
            role="alert"
            className="rounded-lg border border-error-border bg-error-soft px-3 py-2 text-xs text-error"
          >
            {error}
          </p>
        )}

        <Button type="submit" size="lg" loading={loading} className="mt-1 w-full">
          {loading ? 'Ingresando...' : 'Continuar'}
        </Button>
      </form>

      <div className="my-5 flex items-center gap-3">
        <div className="h-px flex-1 bg-border-strong" />
        <span className="text-xs text-muted">o</span>
        <div className="h-px flex-1 bg-border-strong" />
      </div>

      <div className="flex flex-col items-center gap-4 text-sm">
        <p className="text-muted">
          ¿No tienes cuenta?{' '}
          <Link to="/register" className="font-semibold text-primary hover:text-primary-hover">
            Regístrate
          </Link>
        </p>

        <Link
          to="/"
          className="inline-flex items-center gap-1.5 text-xs text-muted transition-colors hover:text-white"
        >
          <ArrowLeft size={14} aria-hidden="true" />
          Volver al inicio
        </Link>
      </div>
    </div>
  )
}
