/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        primary: 'var(--color-primary)',
        'primary-soft': 'var(--color-primary-soft)',
        'primary-border': 'var(--color-primary-border)',
        'primary-hover': 'var(--color-primary-hover)',
        'primary-light': 'var(--color-primary-hover)',
        'primary-deep': 'var(--color-primary-deep)',
        night: 'var(--bg-base)',
        surface: 'var(--bg-surface)',
        card: 'var(--bg-card)',
        'card-hover': 'var(--bg-card-hover)',
        muted: 'var(--text-subdued)',
        border: 'var(--border)',
        'border-strong': 'var(--border-strong)',
        success: 'var(--color-success)',
        'success-soft': 'var(--color-success-soft)',
        warning: 'var(--color-warning)',
        error: 'var(--color-error)',
        'error-soft': 'var(--color-error-soft)',
        'error-border': 'var(--color-error-border)',
        info: 'var(--color-info)',
        white: 'var(--text-base)',
        black: 'var(--color-on-primary)',
      },
      // Color por defecto de `border` (sin color explícito o con una clase que no se genera,
      // como `border-border/60` sobre un var()): gris oscuro en vez de currentColor (blanco).
      borderColor: {
        DEFAULT: 'var(--border)',
      },
      borderRadius: {
        pill: '500px',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'Segoe UI', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
