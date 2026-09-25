import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import * as client from '../api/client'
import type { Role, User } from '../api/client'
import { AuthContext } from './context'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    client.setSessionLostHandler(() => setUser(null))
    // після перезавантаження сторінки сесію відновлюємо через refresh-cookie
    client.refreshSession().then((u) => {
      setUser(u)
      setReady(true)
    })
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    setUser(await client.login(email, password))
  }, [])

  const logout = useCallback(async () => {
    await client.logout()
    setUser(null)
  }, [])

  const hasRole = useCallback((...roles: Role[]) => !!user && roles.includes(user.role), [user])

  const value = useMemo(() => ({ user, ready, login, logout, hasRole }), [user, ready, login, logout, hasRole])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
