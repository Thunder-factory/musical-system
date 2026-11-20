interface Props {
  checked: boolean
  onChange: (checked: boolean) => void
  disabled?: boolean
}

export default function ConsentCheck({ checked, onChange, disabled = false }: Props) {
  return (
    <label
      className={`flex items-start gap-3 rounded-xl bg-card-hover px-4 py-3 text-sm ${
        disabled ? 'cursor-not-allowed opacity-60' : 'cursor-pointer'
      }`}
    >
      <input
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
        className="mt-0.5 h-4 w-4 shrink-0 cursor-pointer accent-[var(--color-primary)]"
      />
      <span className="text-white">
        Confirmo que la foto es mía o tengo permiso de la persona.
        <span className="mt-0.5 block text-xs text-muted">
          La foto y tu clip se borran al terminar; solo guardamos el video final.
        </span>
      </span>
    </label>
  )
}
