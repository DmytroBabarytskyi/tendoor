import { createContext, useContext } from 'react'

export type ThemeChoice = 'light' | 'dark' | 'system'

export type ThemeState = {
  theme: ThemeChoice
  resolved: 'light' | 'dark'
  setTheme: (t: ThemeChoice) => void
}

export const ThemeContext = createContext<ThemeState | null>(null)

export function useTheme(): ThemeState {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error('useTheme використовується поза ThemeProvider')
  return ctx
}
