import { useState, type FormEvent, type ChangeEvent } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import client from '../../api/client'
import { ENDPOINTS } from '../../api/endpoints'
import { useAuthStore } from '../../store/auth.store'

export default function RegisterPage() {
  const navigate = useNavigate()
  const { setTokens, setUser } = useAuthStore()
  const [form, setForm] = useState({ email: '', password: '', full_name: '' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [showPassword, setShowPassword] = useState(false)

  function handleChange(e: ChangeEvent<HTMLInputElement>) {
    setForm((f) => ({ ...f, [e.target.name]: e.target.value }))
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await client.post(ENDPOINTS.auth.register, {
        full_name: form.full_name,
        email: form.email,
        password: form.password,
      })
      const { data } = await client.post(ENDPOINTS.auth.login, {
        email: form.email,
        password: form.password,
      })
      setTokens(data.access, data.refresh)
      const { data: me } = await client.get(ENDPOINTS.auth.me)
      setUser(me)
      navigate(me.role === 'admin' ? '/admin' : '/library')
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: unknown } })?.response?.data
      setError(
        typeof detail === 'string' ? detail : (JSON.stringify(detail) ?? 'Error al registrarse')
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <style>{`
        .register-input:-webkit-autofill,
        .register-input:-webkit-autofill:hover,
        .register-input:-webkit-autofill:focus,
        .register-input:-webkit-autofill:active {
          -webkit-box-shadow: 0 0 0 9999px var(--bg-surface) inset !important;
          box-shadow: 0 0 0 9999px var(--bg-surface) inset !important;
          -webkit-text-fill-color: var(--text-base) !important;
          caret-color: var(--text-base);
        }
        .register-input {
          background-color: var(--bg-surface) !important;
          color: var(--text-base) !important;
        }
        .register-input:focus {
          border-color: var(--color-primary) !important;
        }
      `}</style>
      <div
        className="flex min-h-screen flex-col items-center justify-center bg-night px-4 py-8"
        style={{ fontFamily: "'Helvetica Neue', Helvetica, Arial, sans-serif" }}
      >
        <div className="w-full max-w-[380px] text-center">
          <img src="/logo.png" alt="MusicGen" className="mx-auto mb-5 h-24 w-24 object-contain" />
          <h1 className="text-3xl font-black leading-tight tracking-tight text-white">
            Crea tu cuenta
          </h1>
          <p className="mt-2 text-sm text-muted">Regístrate para empezar a escuchar contenido.</p>

          <form onSubmit={handleSubmit} className="mt-7 flex w-full flex-col gap-4 text-left">
            <div className="flex flex-col gap-1">
              <label htmlFor="full_name" className="text-xs font-bold text-white">
                Nombre completo
              </label>
              <input
                id="full_name"
                type="text"
                name="full_name"
                placeholder="Tu nombre completo"
                value={form.full_name}
                onChange={handleChange}
                required
                autoComplete="name"
                className="register-input h-11 w-full rounded-lg px-3 text-sm outline-none"
                style={{
                  border: '1px solid var(--border-input)',
                  transition: 'border-color 0.15s',
                }}
                onFocus={(e) => (e.currentTarget.style.borderColor = 'var(--text-base)')}
                onBlur={(e) => (e.currentTarget.style.borderColor = 'var(--border-input)')}
              />
            </div>
            <div className="flex flex-col gap-1">
              <label htmlFor="email" className="text-xs font-bold text-white">
                Correo electrónico
              </label>
              <input
                id="email"
                type="email"
                name="email"
                placeholder="tu@email.com"
                value={form.email}
                onChange={handleChange}
                required
                autoComplete="email"
                className="register-input h-11 w-full rounded-lg px-3 text-sm outline-none"
                style={{
                  border: '1px solid var(--border-input)',
                  transition: 'border-color 0.15s',
                }}
                onFocus={(e) => (e.currentTarget.style.borderColor = 'var(--text-base)')}
                onBlur={(e) => (e.currentTarget.style.borderColor = 'var(--border-input)')}
              />
            </div>
            <div className="flex flex-col gap-1">
              <label htmlFor="password" className="text-xs font-bold text-white">
                Contraseña
              </label>
              <div className="relative">
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  name="password"
                  placeholder="Mínimo 8 caracteres"
                  value={form.password}
                  onChange={handleChange}
                  required
                  minLength={8}
                  autoComplete="new-password"
                  className="register-input h-11 w-full rounded-lg px-3 pr-10 text-sm outline-none"
                  style={{
                    border: '1px solid var(--border-input)',
                    transition: 'border-color 0.15s',
                  }}
                  onFocus={(e) => (e.currentTarget.style.borderColor = 'var(--text-base)')}
                  onBlur={(e) => (e.currentTarget.style.borderColor = 'var(--border-input)')}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((p) => !p)}
                  aria-label={showPassword ? 'Ocultar contraseña' : 'Mostrar contraseña'}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted transition-colors hover:text-white"
                >
                  {showPassword ? (
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      width="16"
                      height="16"
                      fill="currentColor"
                      viewBox="0 0 16 16"
                    >
                      <path d="M16 8s-3-5.5-8-5.5S0 8 0 8s3 5.5 8 5.5S16 8 16 8M1.173 8a13 13 0 0 1 1.66-2.043C4.12 4.668 5.88 3.5 8 3.5s3.879 1.168 5.168 2.457A13 13 0 0 1 14.828 8q-.086.13-.195.288c-.335.48-.83 1.12-1.465 1.755C11.879 11.332 10.119 12.5 8 12.5s-3.879-1.168-5.168-2.457A13 13 0 0 1 1.172 8z" />
                      <path d="M8 5.5a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5M4.5 8a3.5 3.5 0 1 1 7 0 3.5 3.5 0 0 1-7 0" />
                    </svg>
                  ) : (
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      width="16"
                      height="16"
                      fill="currentColor"
                      viewBox="0 0 16 16"
                    >
                      <path d="M13.359 11.238C15.06 9.72 16 8 16 8s-3-5.5-8-5.5a7 7 0 0 0-2.79.588l.77.771A6 6 0 0 1 8 3.5c2.12 0 3.879 1.168 5.168 2.457A13 13 0 0 1 14.828 8q-.086.13-.195.288c-.335.48-.83 1.12-1.465 1.755q-.247.248-.517.486z" />
                      <path d="M11.297 9.176a3.5 3.5 0 0 0-4.474-4.474l.823.823a2.5 2.5 0 0 1 2.829 2.829zm-2.943 1.299.822.822a3.5 3.5 0 0 1-4.474-4.474l.823.823a2.5 2.5 0 0 0 2.829 2.829" />
                      <path d="M3.35 5.47q-.27.24-.518.487A13 13 0 0 0 1.172 8l.195.288c.335.48.83 1.12 1.465 1.755C4.121 11.332 5.881 12.5 8 12.5c.716 0 1.39-.133 2.02-.36l.77.772A7 7 0 0 1 8 13.5C3 13.5 0 8 0 8s.939-1.721 2.641-3.238l.708.709zm10.296 8.884-12-12 .708-.708 12 12z" />
                    </svg>
                  )}
                </button>
              </div>
            </div>
            {error && (
              <p
                role="alert"
                className="rounded-lg border border-error-border bg-error-soft px-3 py-2 text-xs text-error"
              >
                {error}
              </p>
            )}
            <button
              type="submit"
              disabled={loading}
              className="mt-1 h-11 w-full rounded-lg text-sm font-bold text-black transition-all duration-150 disabled:cursor-not-allowed disabled:opacity-50"
              style={{
                background: 'var(--color-primary)',
                letterSpacing: '0.01em',
                fontFamily: 'inherit',
              }}
              onMouseEnter={(e) => {
                if (!loading) {
                  e.currentTarget.style.background = 'var(--color-primary-hover)'
                }
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'var(--color-primary)'
              }}
            >
              {loading ? 'Creando cuenta...' : 'Registrarse'}
            </button>
          </form>
          <div className="my-6 flex w-full items-center gap-3">
            <div className="h-px flex-1 bg-border-strong" />
            <span className="text-xs text-muted">o</span>
            <div className="h-px flex-1 bg-border-strong" />
          </div>
          <div className="flex items-center justify-center gap-2">
            <p className="text-sm text-muted">¿Ya tenés cuenta?</p>
            <Link
              to="/login"
              className="inline-block text-sm font-bold text-primary transition-colors hover:text-primary-light"
            >
              Iniciar sesión
            </Link>
          </div>
          <button
            type="button"
            onClick={() => navigate('/')}
            className="mt-6 cursor-pointer border-none bg-transparent text-sm text-muted transition-colors hover:text-white"
          >
            ← Volver al inicio
          </button>
        </div>
        <p className="mt-6 max-w-[380px] text-center text-[10px] leading-relaxed text-muted">
          Este sitio está protegido por reCAPTCHA. Se aplican los{' '}
          <a
            href="https://policies.google.com/terms"
            target="_blank"
            rel="noopener noreferrer"
            className="underline"
            onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--color-primary)')}
            onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--text-subdued)')}
          >
            Términos del servicio
          </a>{' '}
          y la{' '}
          <a
            href="https://policies.google.com/privacy"
            target="_blank"
            rel="noopener noreferrer"
            className="underline"
            onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--color-primary)')}
            onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--text-subdued)')}
          >
            Política de privacidad
          </a>{' '}
          de Google.
        </p>
      </div>
    </>
  )
}
