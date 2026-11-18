import { createContext, useContext, useEffect, useRef, useState } from 'react'
import { flushSync } from 'react-dom'

const KEY = 'lapor_theme'
const ThemeContext = createContext(null)
const media = () => window.matchMedia('(prefers-color-scheme: dark)')

function read() {
  try {
    return localStorage.getItem(KEY) || 'system'
  } catch {
    return 'system'
  }
}

export function ThemeProvider({ children }) {
  const [theme, setThemeState] = useState(read)
  const [systemDark, setSystemDark] = useState(() => media().matches)
  const timerRef = useRef(null)

  useEffect(() => {
    const m = media()
    const onChange = (e) => setSystemDark(e.matches)
    m.addEventListener('change', onChange)
    return () => m.removeEventListener('change', onChange)
  }, [])

  const dark = theme === 'dark' || (theme === 'system' && systemDark)

  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark)
    try {
      localStorage.setItem(KEY, theme)
    } catch {
    }
  }, [theme, dark])

  const setTheme = (next) => {
    const nextDark = next === 'dark' || (next === 'system' && media().matches)
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches

    if (!reduced && typeof document.startViewTransition === 'function') {
      document.startViewTransition(() => {
        document.documentElement.classList.toggle('dark', nextDark)
        flushSync(() => setThemeState(next))
      })
      return
    }

    document.documentElement.classList.add('theme-transition')
    window.clearTimeout(timerRef.current)
    setThemeState(next)
    timerRef.current = window.setTimeout(() => {
      document.documentElement.classList.remove('theme-transition')
    }, 380)
  }

  return <ThemeContext.Provider value={{ theme, setTheme, dark }}>{children}</ThemeContext.Provider>
}

export const useTheme = () => useContext(ThemeContext)
