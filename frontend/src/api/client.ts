// HTTP-клієнт API. Access-токен живе лише в пам'яті (недоступний після перезавантаження сторінки
// і для сторонніх скриптів через localStorage), refresh-токен — у httpOnly cookie на бекенді.

export type Role = 'admin' | 'analyst' | 'auditor'

export type User = {
  id: number
  email: string
  full_name: string
  role: Role
  is_active: boolean
  created_at?: string | null
  last_login_at?: string | null
}

type TokenResponse = { access_token: string; expires_in: number; user: User }

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

let accessToken: string | null = null
let refreshing: Promise<User | null> | null = null
let onSessionLost: (() => void) | null = null

export function setSessionLostHandler(handler: () => void) {
  onSessionLost = handler
}

async function errorMessage(resp: Response): Promise<string> {
  try {
    const body = await resp.json()
    if (typeof body.detail === 'string') return body.detail
    if (Array.isArray(body.detail)) return body.detail.map((d: { msg: string }) => d.msg).join('; ')
  } catch {
    /* не JSON */
  }
  return `Помилка ${resp.status}`
}

/** Оновлює access-токен через cookie; паралельні виклики чекають на один запит. */
export function refreshSession(): Promise<User | null> {
  refreshing ??= fetch('/api/auth/refresh', { method: 'POST', credentials: 'include' })
    .then(async (r) => {
      if (!r.ok) {
        accessToken = null
        return null
      }
      const data = (await r.json()) as TokenResponse
      accessToken = data.access_token
      return data.user
    })
    .finally(() => {
      refreshing = null
    })
  return refreshing
}

export async function api<T>(path: string, init: RequestInit = {}, retry = true): Promise<T> {
  const headers = new Headers(init.headers)
  if (init.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
  if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`)

  const resp = await fetch(`/api${path}`, { ...init, headers, credentials: 'include' })
  if (resp.status === 401 && retry && !path.startsWith('/auth/')) {
    if (await refreshSession()) return api<T>(path, init, false)
    onSessionLost?.()
  }
  if (!resp.ok) throw new ApiError(resp.status, await errorMessage(resp))
  if (resp.status === 204) return undefined as T
  return (await resp.json()) as T
}

/** Завантаження файлу (звіту) з тими самими правилами автентифікації, що й api(). */
export async function download(path: string, fallbackName: string): Promise<void> {
  const send = () =>
    fetch(`/api${path}`, {
      credentials: 'include',
      headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
    })
  let resp = await send()
  if (resp.status === 401 && (await refreshSession())) resp = await send()
  if (!resp.ok) throw new ApiError(resp.status, await errorMessage(resp))
  const name = /filename="([^"]+)"/.exec(resp.headers.get('Content-Disposition') ?? '')?.[1] ?? fallbackName
  const url = URL.createObjectURL(await resp.blob())
  const a = Object.assign(document.createElement('a'), { href: url, download: name })
  a.click()
  URL.revokeObjectURL(url)
}

export async function login(email: string, password: string): Promise<User> {
  const data = await api<TokenResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  })
  accessToken = data.access_token
  return data.user
}

export async function logout(): Promise<void> {
  try {
    await api('/auth/logout', { method: 'POST' })
  } finally {
    accessToken = null
  }
}

export async function changePassword(oldPassword: string, newPassword: string): Promise<void> {
  const data = await api<TokenResponse>('/auth/change-password', {
    method: 'POST',
    body: JSON.stringify({ old_password: oldPassword, new_password: newPassword }),
  })
  accessToken = data.access_token
}

export const ROLE_NAMES: Record<Role, string> = {
  admin: 'Адміністратор',
  analyst: 'Аналітик',
  auditor: 'Аудитор',
}
