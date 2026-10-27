import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { APP_NAME } from '../lib/constants'
import ThemeToggle from './ThemeToggle'
import { ShieldIcon } from './ui'

const LINKS = {
  pelapor: [
    { to: '/pelapor', label: 'My Reports', end: true },
    { to: '/pelapor/lapor-baru', label: 'Create Report' },
    { to: '/pelapor/verifikasi', label: 'ID Verification' },
    { to: '/pelapor/profil', label: 'My Data' },
  ],
  petugas: [
    { to: '/petugas', label: 'Case Queue', end: true },
    { to: '/petugas/verifikasi', label: 'ID Verification' },
    { to: '/petugas/statistik', label: 'Statistics' },
    { to: '/petugas/audit', label: 'Audit Log' },
  ],
}

export default function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const links = LINKS[user.role] ?? []

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800">
      <header className="sticky top-0 z-10 border-b border-slate-200 bg-surface">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
          <div className="flex items-center gap-2 font-semibold text-brand-700">
            <ShieldIcon />
            <span>{APP_NAME}</span>
            <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[11px] font-medium text-slate-500 uppercase">
              {user.role}
            </span>
          </div>
          <nav className="flex flex-wrap gap-1">
            {links.map((l) => (
              <NavLink
                key={l.to}
                to={l.to}
                end={l.end}
                className={({ isActive }) =>
                  `border-b-2 px-3 py-1.5 text-sm transition-colors duration-200 ease-standard ${isActive ? 'border-brand-600 font-semibold text-brand-700' : 'border-transparent text-slate-700 hover:text-brand-700'}`
                }
              >
                {l.label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-3 text-sm">
            <ThemeToggle />
            <span className="hidden text-slate-500 sm:inline">{user.full_name}</span>
            <button
              className="btn-secondary btn-sm"
              onClick={() => {
                logout()
                navigate('/login')
              }}
            >
              Logout
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-8">
        <Outlet />
      </main>
    </div>
  )
}
