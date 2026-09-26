import { useEffect, useState } from 'react'
import { api } from '@/api/client'

export type Badges = { in_work: number; returned: number; my_submitted: number; to_review: number; registrations?: number }

const listeners = new Set<() => void>()

/** Перечитати лічильники одразу після дії (вердикт, погодження, розгляд заявки). */
export function refreshBadges() {
  listeners.forEach((l) => l())
}

/** Лічильники черг для меню й огляду; оновлюються раз на 30 с і після дій користувача. */
export function useBadges(): Badges | null {
  const [badges, setBadges] = useState<Badges | null>(null)
  useEffect(() => {
    let alive = true
    const load = () => api<Badges>('/badges').then((b) => alive && setBadges(b), () => undefined)
    load()
    const timer = setInterval(load, 30_000)
    listeners.add(load)
    return () => {
      alive = false
      clearInterval(timer)
      listeners.delete(load)
    }
  }, [])
  return badges
}
