import { Outlet } from 'react-router-dom'

export default function AuthLayout() {
  return (
    <div className="min-h-screen overflow-y-auto bg-night flex items-center justify-center p-6">
      <Outlet />
    </div>
  )
}
