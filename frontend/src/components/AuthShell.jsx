import { APP_NAME, OFFICER_UNIT } from '../lib/constants'
import ThemeToggle from './ThemeToggle'
import { ShieldIcon } from './ui'

export default function AuthShell({ title, subtitle, children }) {
  return (
    <div className="grid min-h-screen bg-slate-50 text-slate-800 lg:grid-cols-2">
      <aside className="hidden flex-col justify-between border-r border-slate-200 bg-black p-10 text-white lg:flex">
        <div className="flex items-center gap-2 text-lg font-semibold">
          <ShieldIcon className="h-6 w-6 text-brand-solid" /> {APP_NAME}
        </div>
        <div className="space-y-4">
          <div className="h-1 w-12 bg-brand-solid" />
          <h2 className="text-3xl leading-tight font-semibold">
            Report incidents securely on campus.
          </h2>
          <ul className="space-y-2 text-sm text-white/80">
            <li>• Your identity, ID card, and evidence are encrypted before storage.</li>
            <li>• Only you can download the original files you submit.</li>
            <li>• {OFFICER_UNIT} officers see your identity in masked form.</li>
            <li>• You decide which evidence officers are allowed to view.</li>
          </ul>
        </div>
        <p className="text-xs text-white/70">
          Data processed in accordance with personal data protection regulations.
        </p>
      </aside>
      <main className="relative flex items-center justify-center p-6">
        <div className="absolute top-4 right-4">
          <ThemeToggle />
        </div>
        <div className="w-full max-w-md">
          <div className="mb-6 flex items-center gap-2 font-semibold text-brand-700 lg:hidden">
            <ShieldIcon /> {APP_NAME}
          </div>
          <h1 className="text-2xl font-semibold text-slate-900">{title}</h1>
          {subtitle && <p className="mt-1 mb-6 text-sm text-slate-500">{subtitle}</p>}
          {children}
        </div>
      </main>
    </div>
  )
}
