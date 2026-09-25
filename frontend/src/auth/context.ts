import { createContext, useContext } from 'react'
import type { Role, User } from '../api/client'

export type AuthState = {
  user: User | null
  ready: boolean // сесію відновлено (або з'ясовано, що її немає)
  login: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
  hasRole: (...roles: Role[]) => boolean
}

export const AuthContext = createContext<AuthState | null>(null)

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth використовується поза AuthProvider')
  return ctx
}
