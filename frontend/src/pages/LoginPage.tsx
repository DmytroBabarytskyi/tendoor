import { motion } from 'motion/react'
import { ArrowRight, Eye, EyeOff, LoaderCircle, OctagonX } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router'
import { useAuth } from '@/auth/context'
import GravityGrid from '@/components/gravity/GravityGrid'
import Logo from '@/components/Logo'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

const FACTS = [
  ['~1 хв', 'від вибору товарів і періоду до переліку підозрілих цін'],
  ['0–100', 'оцінка ризику з поясненням, чому ціна підозріла'],
  ['Prozorro', 'відкриті дані публічних закупівель України'],
]

export default function LoginPage() {
  const { user, login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [show, setShow] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const from = (location.state as { from?: string } | null)?.from ?? '/'

  if (user) return <Navigate to={from} replace />

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      await login(email.trim(), password)
      navigate(from, { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="relative min-h-svh overflow-hidden bg-background">
      <GravityGrid cursorStrength={0.9} />
      {/* м'яке світло від центру: сітка тьмяніє до країв */}
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_center,transparent_20%,var(--background)_78%)]" />

      <div className="relative mx-auto grid min-h-svh max-w-6xl items-center gap-10 px-6 py-10 lg:grid-cols-[1.15fr_1fr]">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
          className="pointer-events-none select-none"
        >
          <Logo className="mb-10" />
          <h1 className="max-w-xl text-4xl leading-[1.1] font-semibold text-balance sm:text-5xl">
            Ціна, що <span className="text-primary italic">не збігається</span> з ринком, — помітна одразу.
          </h1>
          <p className="mt-5 max-w-lg text-base text-muted-foreground text-pretty">
            Tendoor порівнює ціни однорідних товарів у відкритих даних Prozorro, знаходить аномальні пропозиції
            методами машинного навчання й пояснює кожне рішення аудитору.
          </p>
          <dl className="mt-10 hidden grid-cols-3 gap-6 sm:grid">
            {FACTS.map(([k, v]) => (
              <div key={k} className="border-l-2 border-primary/40 pl-3">
                <dt className="font-serif text-2xl font-semibold">{k}</dt>
                <dd className="mt-1 text-xs text-muted-foreground">{v}</dd>
              </div>
            ))}
          </dl>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 16, scale: 0.98 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ duration: 0.6, delay: 0.1, ease: [0.22, 1, 0.36, 1] }}
          className="w-full max-w-sm justify-self-center lg:justify-self-end"
        >
          <form
            onSubmit={submit}
            data-no-ripple
            className="rounded-2xl border bg-card/85 p-7 shadow-[0_20px_60px_-20px_rgba(80,50,20,0.25)] backdrop-blur-xl"
          >
            <h2 className="text-2xl font-semibold">Вхід</h2>
            <p className="mt-1 text-sm text-muted-foreground">Обліковий запис видає адміністратор системи.</p>

            {error && (
              <div role="alert" className="mt-5 flex items-start gap-2 rounded-lg bg-critical-soft px-3 py-2.5 text-sm text-critical">
                <OctagonX className="mt-0.5 size-4 shrink-0" />
                {error}
              </div>
            )}

            <div className="mt-6 space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  autoComplete="username"
                  autoFocus
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="h-10 bg-background/70"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="password">Пароль</Label>
                <div className="relative">
                  <Input
                    id="password"
                    type={show ? 'text' : 'password'}
                    autoComplete="current-password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="h-10 bg-background/70 pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShow((s) => !s)}
                    className="absolute inset-y-0 right-0 grid w-10 place-items-center text-muted-foreground hover:text-foreground"
                    aria-label={show ? 'Приховати пароль' : 'Показати пароль'}
                  >
                    {show ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                  </button>
                </div>
              </div>
            </div>
            <Button type="submit" className="mt-6 h-10 w-full" disabled={loading}>
              {loading ? <LoaderCircle className="animate-spin" /> : null}
              Увійти
              {!loading && <ArrowRight />}
            </Button>
          </form>
        </motion.div>
      </div>
    </div>
  )
}
