import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { ThemeContext, type ThemeChoice } from './context'

const KEY = 'tendoor-theme'
const media = () => window.matchMedia('(prefers-color-scheme: dark)')

// вибір теми — зручність окремого переглядача, тож localStorage; недоступне сховище не ламає застосунок
function stored(): ThemeChoice {
  try {
    const v = localStorage.getItem(KEY)
    return v === 'light' || v === 'dark' ? v : 'system'
  } catch {
    return 'system'
  }
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<ThemeChoice>(stored)
  const [systemDark, setSystemDark] = useState(() => media().matches)

  useEffect(() => {
    const m = media()
    const on = (e: MediaQueryListEvent) => setSystemDark(e.matches)
    m.addEventListener('change', on)
    return () => m.removeEventListener('change', on)
  }, [])

  const resolved = theme === 'system' ? (systemDark ? 'dark' : 'light') : theme

  useEffect(() => {
    document.documentElement.classList.toggle('dark', resolved === 'dark')
  }, [resolved])

  const setTheme = useCallback((t: ThemeChoice) => {
    setThemeState(t)
    try {
      if (t === 'system') localStorage.removeItem(KEY)
      else localStorage.setItem(KEY, t)
    } catch {
      /* сховище недоступне — тема діє до перезавантаження */
    }
  }, [])

  const value = useMemo(() => ({ theme, resolved, setTheme }), [theme, resolved, setTheme])
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}
