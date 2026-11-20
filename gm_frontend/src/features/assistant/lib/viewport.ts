const QUERY = '(max-width: 639px)'

/** Consulta puntual (al hacer clic) de si la pantalla es de móvil. */
export function isMobileViewport(): boolean {
  try {
    return window.matchMedia(QUERY).matches
  } catch {
    return false
  }
}
