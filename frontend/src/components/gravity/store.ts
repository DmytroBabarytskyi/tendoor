// Спільне сховище «мас» для гравітаційної сітки: курсор, перетягувані картки тощо.
// Координати — у пікселях вікна (clientX/clientY), тож джерелом може бути будь-який компонент.

export type Mass = { x: number; y: number; strength: number }
export type Ripple = { x: number; y: number; start: number; power: number }

const masses = new Map<string, Mass>()
const ripples: Ripple[] = []
const listeners = new Set<() => void>()

function wake() {
  listeners.forEach((l) => l())
}

export const gravity = {
  setMass(id: string, m: Mass) {
    masses.set(id, m)
    wake()
  },
  removeMass(id: string) {
    if (masses.delete(id)) wake()
  },
  ripple(x: number, y: number, power = 1) {
    ripples.push({ x, y, start: performance.now(), power })
    wake()
  },
  masses: () => masses,
  ripples: () => ripples,
  subscribe(l: () => void) {
    listeners.add(l)
    return () => {
      listeners.delete(l)
    }
  },
}
