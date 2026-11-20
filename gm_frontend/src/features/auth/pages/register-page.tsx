import { useState, type ChangeEvent, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowLeft, Eye, EyeOff } from 'lucide-react'

import { Button, FormField, Input } from '../../../components/ui'
import { useAuthStore } from '../../../store/auth.store'
import { formatAuthError, getMeRequest, loginRequest, registerRequest } from '../api/auth.api'

export default function RegisterPage() {
  const navigate = useNavigate()
  const setTokens = useAuthStore((s) => s.setTokens)
  const setUser = useAuthStore((s) => s.setUser)

  const [form, setForm] = useState({ full_name: '', email: '', password: '' })
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  function handleChange(event: ChangeEvent<HTMLInputElement>) {
    const { name, value } = event.target
    setForm((prev) => ({ ...prev, [name]: value }))
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    setLoading(true)
    try {
      await registerRequest({
        full_name: form.full_name.trim(),
        email: form.email.trim(),
        password: form.password,
      })
      const tokens = await loginRequest(form.email.trim(), form.password)
      setTokens(tokens.access, tokens.refresh)
      const me = await getMeRequest()
      setUser(me)
      navigate(me.role === 'admin' ? '/admin' : '/inicio', { replace: true })
    } catch (err: unknown) {
      setError(formatAuthError(err, 'No se pudo completar el registro.'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="w-full max-w-[400px] rounded-2xl border border-border bg-surface/90 p-6 sm:p-8 shadow-[var(--shadow)]">
      <div className="text-center">
        <img src="/logo.png" alt="MusicAI" className="mx-auto mb-4 h-16 w-16 object-contain" />
        <h1 className="text-2xl font-bold tracking-tight text-white">Crea tu cuenta</h1>
        <p className="mt-1.5 text-sm text-muted">
          Únete a MusicAI y empieza a crear música con inteligencia artificial.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="mt-6 flex flex-col gap-4">
        <FormField label="Nombre completo" required>
          <Input
            name="full_name"
            type="text"
            placeholder="Tu nombre completo"
            value={form.full_name}
            onChange={handleChange}
            required
            autoComplete="name"
            disabled={loading}
          />
        </FormField>

        <FormField label="Correo electrónico" required>
          <Input
            name="email"
            type="email"
            placeholder="tu@email.com"
            value={form.email}
            onChange={handleChange}
            required
            autoComplete="email"
            disabled={loading}
          />
        </FormField>

        <FormField label="Contraseña" hint="Mínimo 8 caracteres." required>
          <div className="relative">
            <Input
              name="password"
              type={showPassword ? 'text' : 'password'}
              placeholder="Mínimo 8 caracteres"
              value={form.password}
              onChange={handleChange}
              required
              minLength={8}
              autoComplete="new-password"
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
          {loading ? 'Creando cuenta...' : 'Registrarse'}
        </Button>
      </form>

      <div className="my-5 flex items-center gap-3">
        <div className="h-px flex-1 bg-border-strong" />
        <span className="text-xs text-muted">o</span>
        <div className="h-px flex-1 bg-border-strong" />
      </div>

      <div className="flex flex-col items-center gap-4 text-sm">
        <p className="text-muted">
          ¿Ya tienes cuenta?{' '}
          <Link to="/login" className="font-semibold text-primary hover:text-primary-hover">
            Iniciar sesión
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
