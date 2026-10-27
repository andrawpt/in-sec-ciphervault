import { useTheme } from '../context/ThemeContext'

const OPTIONS = [
  {
    value: 'light',
    label: 'Light',
    icon: (
      <path d="M12 4V2m0 20v-2m8-8h2M2 12h2m13.66-5.66 1.41-1.41M4.93 19.07l1.41-1.41m0-11.32L4.93 4.93m14.14 14.14-1.41-1.41M12 17a5 5 0 1 0 0-10 5 5 0 0 0 0 10Z" />
    ),
  },
  { value: 'dark', label: 'Dark', icon: <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z" /> },
  {
    value: 'system',
    label: 'System',
    icon: <path d="M4 5h16v11H4zM8 20h8m-4-4v4" />,
  },
]

export default function ThemeToggle() {
  const { theme, setTheme } = useTheme()
  return (
    <div className="inline-flex rounded-lg border border-slate-200 bg-surface p-0.5" role="radiogroup" aria-label="Display theme">
      {OPTIONS.map((o) => (
        <button
          key={o.value}
          type="button"
          role="radio"
          aria-checked={theme === o.value}
          title={o.label}
          onClick={() => setTheme(o.value)}
          className={`rounded-md p-1.5 ${theme === o.value ? 'bg-slate-100 text-slate-900' : 'text-slate-500 hover:text-slate-800'}`}
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4" aria-hidden="true">
            {o.icon}
          </svg>
          <span className="sr-only">{o.label}</span>
        </button>
      ))}
    </div>
  )
}
