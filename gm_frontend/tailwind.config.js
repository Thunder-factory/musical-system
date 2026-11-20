/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        primary: 'rgb(var(--color-primary-rgb) / <alpha-value>)',
        'primary-soft': 'var(--color-primary-soft)',
        'primary-border': 'var(--color-primary-border)',
        'primary-hover': 'rgb(var(--color-primary-hover-rgb) / <alpha-value>)',
        'primary-light': 'rgb(var(--color-primary-hover-rgb) / <alpha-value>)',
        'primary-deep': 'rgb(var(--color-primary-deep-rgb) / <alpha-value>)',
        night: 'rgb(var(--bg-base-rgb) / <alpha-value>)',
        surface: 'rgb(var(--bg-surface-rgb) / <alpha-value>)',
        card: 'rgb(var(--bg-card-rgb) / <alpha-value>)',
        'card-hover': 'rgb(var(--bg-card-hover-rgb) / <alpha-value>)',
        muted: 'rgb(var(--text-subdued-rgb) / <alpha-value>)',
        border: 'rgb(var(--border-rgb) / <alpha-value>)',
        'border-strong': 'rgb(var(--border-strong-rgb) / <alpha-value>)',
        success: 'rgb(var(--color-success-rgb) / <alpha-value>)',
        'success-soft': 'var(--color-success-soft)',
        warning: 'rgb(var(--color-warning-rgb) / <alpha-value>)',
        error: 'rgb(var(--color-error-rgb) / <alpha-value>)',
        'error-soft': 'var(--color-error-soft)',
        'error-border': 'var(--color-error-border)',
        info: 'rgb(var(--color-info-rgb) / <alpha-value>)',
        white: 'rgb(var(--text-base-rgb) / <alpha-value>)',
        black: 'rgb(var(--color-on-primary-rgb) / <alpha-value>)',
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
