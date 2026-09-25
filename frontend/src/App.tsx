import { useEffect, useState } from 'react'

type Health = { status: string; version: string; checks: Record<string, string> }

export default function App() {
  const [health, setHealth] = useState<Health | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch('/api/health')
      .then((r) => r.json() as Promise<Health>)
      .then(setHealth)
      .catch((e: unknown) => setError(String(e)))
  }, [])

  return (
    <main>
      <h1>Tendoor</h1>
      <p className="subtitle">Аналітика цінових аномалій публічних закупівель</p>
      <section>
        <h2>Стан системи</h2>
        {error && <p className="bad">API недоступний: {error}</p>}
        {!health && !error && <p>Перевірка…</p>}
        {health && (
          <ul>
            <li>
              API v{health.version}: <b className={health.status === 'ok' ? 'good' : 'bad'}>{health.status}</b>
            </li>
            {Object.entries(health.checks).map(([name, state]) => (
              <li key={name}>
                {name}: <b className={state === 'ok' ? 'good' : 'bad'}>{state}</b>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  )
}
