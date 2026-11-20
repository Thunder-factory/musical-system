import type { AuthUser } from '../../store/auth.store'

function getUserInitials(fullName?: string | null): string {
  if (!fullName) {
    return '?'
  }
  return fullName
    .split(' ')
    .filter(Boolean)
    .map((part) => part[0])
    .join('')
    .slice(0, 2)
    .toUpperCase()
}

export function UserAvatar({ user }: { user: AuthUser | null }) {
  if (user?.avatar_url) {
    return (
      <img
        src={user.avatar_url}
        alt={`Avatar de ${user.full_name}`}
        className="h-8 w-8 shrink-0 rounded-full border-2 border-primary object-cover"
      />
    )
  }

  return (
    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-bold text-black">
      {getUserInitials(user?.full_name)}
    </span>
  )
}
