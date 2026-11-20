import type { FormEvent } from 'react'
import { Search } from 'lucide-react'

import { Input, Select } from '../../../components/ui'

const FILTER_OPTIONS = [
  { value: 'Todos', label: 'Todos los géneros' },
  { value: 'Trending', label: 'Tendencias (48h)' },
  { value: 'reggaeton', label: 'Reggaetón' },
  { value: 'lofi', label: 'Lo-Fi' },
  { value: 'techno', label: 'Techno' },
  { value: 'pop', label: 'Pop' },
  { value: 'rock', label: 'Rock' },
  { value: 'electronic', label: 'Electrónica' },
]

interface CommunityFiltersProps {
  search: string
  activeTag: string
  onSearchChange: (value: string) => void
  onSearchSubmit: (e: FormEvent) => void
  onTagChange: (tag: string) => void
}

export default function CommunityFilters({
  search,
  activeTag,
  onSearchChange,
  onSearchSubmit,
  onTagChange,
}: CommunityFiltersProps) {
  return (
    <div className="flex flex-col gap-4 lg:flex-row lg:items-center">
      <form onSubmit={onSearchSubmit} className="relative w-full lg:flex-1">
        <Input
          type="text"
          placeholder="Buscar canciones o creadores..."
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          aria-label="Buscar canciones o creadores"
          className="pr-11"
        />
        <button
          type="submit"
          aria-label="Buscar"
          className="absolute right-2 top-1/2 flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-md text-muted transition-colors hover:bg-surface hover:text-white"
        >
          <Search size={16} aria-hidden="true" />
        </button>
      </form>

      <div className="w-full lg:w-64 lg:flex-none">
        <Select
          value={activeTag}
          onChange={onTagChange}
          options={FILTER_OPTIONS}
          placeholder="Filtrar por género"
        />
      </div>
    </div>
  )
}
