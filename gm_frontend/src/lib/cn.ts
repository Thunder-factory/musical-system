export type ClassValue =
  | string
  | number
  | boolean
  | null
  | undefined
  | Record<string, boolean | null | undefined>
  | ClassValue[]

/** Une clases CSS condicionales ignorando valores vacíos o falsy. */
export function cn(...inputs: ClassValue[]): string {
  const classes: string[] = []

  for (const input of inputs) {
    if (!input) {
      continue
    }

    if (typeof input === 'string' || typeof input === 'number') {
      classes.push(String(input))
      continue
    }

    if (Array.isArray(input)) {
      const nested = cn(...input)
      if (nested) {
        classes.push(nested)
      }
      continue
    }

    if (typeof input === 'object') {
      for (const [key, enabled] of Object.entries(input)) {
        if (enabled) {
          classes.push(key)
        }
      }
    }
  }

  return classes.join(' ')
}
