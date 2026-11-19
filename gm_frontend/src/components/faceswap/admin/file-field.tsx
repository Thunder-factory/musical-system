import { FILE_INPUT } from '../faceswap-ui'

interface Props {
  label: string
  accept: string
  help?: string
  onChange: (file: File | null) => void
}

/** Campo de archivo con etiqueta y ayuda, estilo de los formularios admin. */
export default function FileField({ label, accept, help, onChange }: Props) {
  return (
    <label className="flex flex-col gap-1.5 text-xs font-bold text-white">
      {label}
      <input
        type="file"
        accept={accept}
        className={FILE_INPUT}
        onChange={(e) => onChange(e.target.files?.[0] ?? null)}
      />
      {help && <span className="font-normal text-muted">{help}</span>}
    </label>
  )
}
