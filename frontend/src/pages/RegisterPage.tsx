import { motion } from 'motion/react'
import { ArrowLeft, CircleCheck, LoaderCircle, OctagonX } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link, Navigate } from 'react-router'
import { api } from '@/api/client'
import { useAuth } from '@/auth/context'
import GravityGrid from '@/components/gravity/GravityGrid'
import Logo from '@/components/Logo'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'

const ROLES = [
  { value: 'auditor', label: 'Аудитор', hint: 'розглядає підозрілі ціни й виносить висновки' },
  { value: 'analyst', label: 'Аналітик', hint: 'завантажує дані й налаштовує аналіз' },
] as const
const MIN_PASSWORD = 10

export default function RegisterPage() {
  const { user } = useAuth()
  const [form, setForm] = useState({ full_name: '', email: '', role: 'auditor', password: '', justification: '' })
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [sent, setSent] = useState(false)
  const mismatch = confirm.length > 0 && confirm !== form.password

  if (user) return <Navigate to="/" replace />

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (mismatch) return
    setBusy(true)
    setError(null)
    try {
      await api('/auth/register', { method: 'POST', body: JSON.stringify({ ...form, justification: form.justification || null }) })
      setSent(true)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="relative min-h-svh overflow-hidden bg-background">
      <GravityGrid cursorStrength={0.9} />
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_center,transparent_20%,var(--background)_78%)]" />
      <div className="relative mx-auto flex min-h-svh max-w-lg flex-col justify-center px-6 py-10">
        <Logo className="mb-8" />
        <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}>
          {sent ? (
            <div className="rounded-2xl border bg-card/85 p-7 shadow-[0_20px_60px_-20px_rgba(80,50,20,0.25)] backdrop-blur-xl" data-no-ripple>
              <CircleCheck className="size-8 text-success" />
              <h1 className="mt-3 text-2xl font-semibold">Заявку надіслано</h1>
              <p className="mt-2 text-sm text-muted-foreground">
                Адміністратор розгляне її та призначить роль. Після погодження увійдіть з email <b>{form.email}</b> і паролем, який ви
                щойно вказали.
              </p>
              <Button asChild variant="outline" className="mt-6">
                <Link to="/login">
                  <ArrowLeft /> До входу
                </Link>
              </Button>
            </div>
          ) : (
            <form onSubmit={submit} data-no-ripple className="rounded-2xl border bg-card/85 p-7 shadow-[0_20px_60px_-20px_rgba(80,50,20,0.25)] backdrop-blur-xl">
              <h1 className="text-2xl font-semibold">Заявка на доступ</h1>
              <p className="mt-1 text-sm text-muted-foreground">Увійти можна буде після погодження адміністратором.</p>
              {error && (
                <div role="alert" className="mt-5 flex items-start gap-2 rounded-lg bg-critical-soft px-3 py-2.5 text-sm text-critical">
                  <OctagonX className="mt-0.5 size-4 shrink-0" />
                  {error}
                </div>
              )}
              <div className="mt-6 space-y-4">
                <div className="space-y-1.5">
                  <Label htmlFor="r-name">Прізвище, ім'я, по батькові</Label>
                  <Input id="r-name" required minLength={2} value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} className="bg-background/70" />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="r-email">Службовий email</Label>
                  <Input id="r-email" type="email" required autoComplete="username" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} className="bg-background/70" />
                </div>
                <div className="space-y-1.5">
                  <Label>Роль</Label>
                  <div className="grid grid-cols-2 gap-2" role="radiogroup">
                    {ROLES.map((r) => (
                      <button
                        key={r.value}
                        type="button"
                        role="radio"
                        aria-checked={form.role === r.value}
                        onClick={() => setForm({ ...form, role: r.value })}
                        className={cn(
                          'rounded-lg border p-3 text-left text-sm transition-colors',
                          form.role === r.value ? 'border-primary bg-primary/10' : 'hover:bg-accent/60',
                        )}
                      >
                        <div className="font-medium">{r.label}</div>
                        <div className="mt-0.5 text-xs text-muted-foreground">{r.hint}</div>
                      </button>
                    ))}
                  </div>
                </div>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-1.5">
                    <Label htmlFor="r-pass">Пароль</Label>
                    <Input id="r-pass" type="password" required minLength={MIN_PASSWORD} autoComplete="new-password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} className="bg-background/70" />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="r-confirm">Повторіть пароль</Label>
                    <Input id="r-confirm" type="password" required autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} aria-invalid={mismatch} className="bg-background/70" />
                  </div>
                </div>
                <p className={cn('text-xs', mismatch ? 'text-critical' : 'text-muted-foreground')}>
                  {mismatch ? 'Паролі не збігаються' : `Щонайменше ${MIN_PASSWORD} символів.`}
                </p>
                <div className="space-y-1.5">
                  <Label htmlFor="r-why">Підрозділ і мета доступу</Label>
                  <Textarea id="r-why" maxLength={1000} value={form.justification} onChange={(e) => setForm({ ...form, justification: e.target.value })} placeholder="Напр.: відділ моніторингу закупівель, перевірка цін на продукти харчування" className="min-h-16 bg-background/70" />
                </div>
              </div>
              <Button type="submit" className="mt-6 h-10 w-full" disabled={busy || mismatch}>
                {busy && <LoaderCircle className="animate-spin" />}
                Надіслати заявку
              </Button>
              <p className="mt-4 text-center text-sm text-muted-foreground">
                Уже маєте доступ?{' '}
                <Link to="/login" className="text-primary underline-offset-4 hover:underline">
                  Увійти
                </Link>
              </p>
            </form>
          )}
        </motion.div>
      </div>
    </div>
  )
}
