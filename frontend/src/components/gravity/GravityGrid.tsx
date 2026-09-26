import { useEffect, useRef } from 'react'
import { cn } from '@/lib/utils'
import { gravity } from './store'

/**
 * Гравітаційна сітка: вузли — пружини з демпфуванням, «маси» (курсор, перетягувані картки) прогинають
 * простір довкола себе, як гравітаційна лінза, клік запускає кільцеву хвилю. Коли енергія згасає,
 * анімація зупиняється (0 % CPU у спокої). З prefers-reduced-motion сітка статична.
 */
type Props = {
  className?: string
  spacing?: number
  cursorStrength?: number // сила «маси» курсора; 0 — курсор не впливає
  interactive?: boolean // клік запускає хвилю
}

const STIFFNESS = 0.055
const DAMPING = 0.86
const SOFTENING = 120 // радіус «ядра» маси, px: без нього поле поблизу центру нескінченне
const PEAK_PULL = 6 // зсув вузла на відстані SOFTENING від маси силою 1, px (максимум поля)
const FIELD = 2 * SOFTENING * PEAK_PULL // |зсув| = s·FIELD·r / (r² + ε²), максимум FIELD / 2ε при r = ε
const MAX_PULL = 16 // обмеження сумарного зсуву від кількох мас, px
const RIPPLE_SPEED = 0.9 // px/мс
const RIPPLE_WIDTH = 46
const RIPPLE_LIFE = 1600 // мс

function cssVar(name: string, fallback: string) {
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return v || fallback
}

export default function GravityGrid({ className, spacing = 38, cursorStrength = 1, interactive = true }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches

    let cols = 0
    let rows = 0
    let rest = new Float32Array(0) // x, y спокою
    let disp = new Float32Array(0) // зсув
    let vel = new Float32Array(0)
    let rect = canvas.getBoundingClientRect()
    let frame = 0
    let running = false
    let colors = { line: '', glow: '' }

    const readColors = () => {
      colors = { line: cssVar('--grid-line', 'rgba(120,100,80,.15)'), glow: cssVar('--grid-glow', 'rgba(180,83,47,.5)') }
    }

    const layout = () => {
      rect = canvas.getBoundingClientRect()
      const dpr = Math.min(window.devicePixelRatio || 1, 2)
      canvas.width = Math.round(rect.width * dpr)
      canvas.height = Math.round(rect.height * dpr)
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      cols = Math.ceil(rect.width / spacing) + 3
      rows = Math.ceil(rect.height / spacing) + 3
      const offX = ((rect.width % spacing) - spacing * 2) / 2
      const offY = ((rect.height % spacing) - spacing * 2) / 2
      rest = new Float32Array(cols * rows * 2)
      disp = new Float32Array(cols * rows * 2)
      vel = new Float32Array(cols * rows * 2)
      for (let j = 0; j < rows; j++)
        for (let i = 0; i < cols; i++) {
          const k = (j * cols + i) * 2
          rest[k] = offX + i * spacing
          rest[k + 1] = offY + j * spacing
        }
    }

    const step = (now: number) => {
      const masses = [...gravity.masses().values()].map((m) => ({
        x: m.x - rect.left,
        y: m.y - rect.top,
        s: m.strength,
      }))
      const ripples = gravity.ripples()
      for (let r = ripples.length - 1; r >= 0; r--) if (now - ripples[r].start > RIPPLE_LIFE) ripples.splice(r, 1)
      let energy = 0
      const n = cols * rows
      for (let p = 0; p < n; p++) {
        const k = p * 2
        const x = rest[k]
        const y = rest[k + 1]
        // цільовий зсув: притягання до мас (поле спадає як r / (r² + ε²))
        let tx = 0
        let ty = 0
        for (const m of masses) {
          const dx = m.x - x
          const dy = m.y - y
          const d2 = dx * dx + dy * dy
          const f = (m.s * FIELD) / (d2 + SOFTENING * SOFTENING)
          tx += dx * f
          ty += dy * f
        }
        const len = Math.hypot(tx, ty)
        if (len > MAX_PULL) {
          tx = (tx / len) * MAX_PULL
          ty = (ty / len) * MAX_PULL
        }
        // хвилі: поштовх назовні, коли фронт кільця проходить вузол
        for (const w of ripples) {
          const age = now - w.start
          const radius = age * RIPPLE_SPEED
          const dx = x - (w.x - rect.left)
          const dy = y - (w.y - rect.top)
          const d = Math.hypot(dx, dy) || 1
          const band = 1 - Math.abs(d - radius) / RIPPLE_WIDTH
          if (band > 0) {
            const amp = band * (1 - age / RIPPLE_LIFE) * 2.2 * w.power
            vel[k] += (dx / d) * amp
            vel[k + 1] += (dy / d) * amp
          }
        }
        vel[k] = (vel[k] + (tx - disp[k]) * STIFFNESS) * DAMPING
        vel[k + 1] = (vel[k + 1] + (ty - disp[k + 1]) * STIFFNESS) * DAMPING
        disp[k] += vel[k]
        disp[k + 1] += vel[k + 1]
        energy += Math.abs(vel[k]) + Math.abs(vel[k + 1])
      }
      return energy / n > 0.002 || ripples.length > 0
    }

    const draw = () => {
      ctx.clearRect(0, 0, rect.width, rect.height)
      const px = (i: number, j: number) => {
        const k = (j * cols + i) * 2
        return [rest[k] + disp[k], rest[k + 1] + disp[k + 1], Math.hypot(disp[k], disp[k + 1])] as const
      }
      // основна сітка — одним шляхом
      ctx.lineWidth = 1
      ctx.strokeStyle = colors.line
      ctx.beginPath()
      for (let j = 0; j < rows; j++) {
        for (let i = 0; i < cols; i++) {
          const [x, y] = px(i, j)
          if (i === 0) ctx.moveTo(x, y)
          else ctx.lineTo(x, y)
        }
      }
      for (let i = 0; i < cols; i++) {
        for (let j = 0; j < rows; j++) {
          const [x, y] = px(i, j)
          if (j === 0) ctx.moveTo(x, y)
          else ctx.lineTo(x, y)
        }
      }
      ctx.stroke()
      // прогнуті ділянки підсвічуються акцентом пропорційно до зсуву
      ctx.strokeStyle = colors.glow
      for (const [lo, hi, alpha] of [
        [2, 4, 0.16],
        [4, 7, 0.32],
        [7, 1e9, 0.5],
      ] as const) {
        ctx.globalAlpha = alpha
        ctx.beginPath()
        for (let j = 0; j < rows; j++)
          for (let i = 0; i < cols; i++) {
            const [x, y, d] = px(i, j)
            if (d < lo || d >= hi) continue
            if (i + 1 < cols) {
              const [x2, y2] = px(i + 1, j)
              ctx.moveTo(x, y)
              ctx.lineTo(x2, y2)
            }
            if (j + 1 < rows) {
              const [x2, y2] = px(i, j + 1)
              ctx.moveTo(x, y)
              ctx.lineTo(x2, y2)
            }
          }
        ctx.stroke()
      }
      ctx.globalAlpha = 1
      // вузли
      ctx.fillStyle = colors.line
      for (let j = 0; j < rows; j++)
        for (let i = 0; i < cols; i++) {
          const [x, y, d] = px(i, j)
          const r = 1 + Math.min(d / 5, 1.4)
          ctx.globalAlpha = d > 2.5 ? 0.9 : 0.55
          ctx.fillRect(x - r / 2, y - r / 2, r, r)
        }
      ctx.globalAlpha = 1
    }

    const loop = (now: number) => {
      const active = step(now)
      draw()
      if (active && !document.hidden) frame = requestAnimationFrame(loop)
      else running = false
    }

    const start = () => {
      if (reduced || running) return
      running = true
      frame = requestAnimationFrame(loop)
    }

    readColors()
    layout()
    draw()

    const onMove = (e: PointerEvent) => {
      if (cursorStrength <= 0) return
      const inside = e.clientX >= rect.left && e.clientX <= rect.right && e.clientY >= rect.top && e.clientY <= rect.bottom
      if (inside) gravity.setMass('cursor', { x: e.clientX, y: e.clientY, strength: cursorStrength })
      else gravity.removeMass('cursor')
    }
    const onLeave = () => gravity.removeMass('cursor')
    const onDown = (e: PointerEvent) => {
      if (!interactive) return
      const t = e.target as HTMLElement | null
      // хвиля лише від кліку по тлу, а не по кнопках і полях
      if (t?.closest('button, a, input, textarea, select, [role="button"], [data-no-ripple]')) return
      if (e.clientX >= rect.left && e.clientX <= rect.right && e.clientY >= rect.top && e.clientY <= rect.bottom)
        gravity.ripple(e.clientX, e.clientY)
    }
    const resize = new ResizeObserver(() => {
      layout()
      draw()
      start()
    })
    resize.observe(canvas)
    const themeObserver = new MutationObserver(() => {
      readColors()
      draw()
    })
    themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] })
    const onScroll = () => {
      rect = canvas.getBoundingClientRect()
    }
    const unsubscribe = gravity.subscribe(start)
    window.addEventListener('pointermove', onMove, { passive: true })
    window.addEventListener('pointerdown', onDown, { passive: true })
    document.addEventListener('pointerleave', onLeave)
    window.addEventListener('scroll', onScroll, { passive: true, capture: true })
    return () => {
      cancelAnimationFrame(frame)
      unsubscribe()
      resize.disconnect()
      themeObserver.disconnect()
      gravity.removeMass('cursor')
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerdown', onDown)
      document.removeEventListener('pointerleave', onLeave)
      window.removeEventListener('scroll', onScroll, { capture: true })
    }
  }, [spacing, cursorStrength, interactive])

  return <canvas ref={canvasRef} aria-hidden className={cn('pointer-events-none absolute inset-0 size-full', className)} />
}
