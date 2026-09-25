import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const user = { id: 1, email: 'a@tendoor.dev', full_name: 'A', role: 'auditor', is_active: true }
const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

// модуль тримає токен у змінній модуля, тому кожен тест отримує свіжу копію
async function freshClient() {
  vi.resetModules()
  return import('./client')
}

let fetchMock: ReturnType<typeof vi.fn>

beforeEach(() => {
  fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
})
afterEach(() => vi.unstubAllGlobals())

const authHeader = (call: unknown[]) => new Headers((call[1] as RequestInit).headers).get('Authorization')

describe('api()', () => {
  it('attaches the access token after login and sends JSON bodies', async () => {
    const c = await freshClient()
    fetchMock.mockResolvedValueOnce(json(200, { access_token: 'T1', expires_in: 900, user }))
    fetchMock.mockResolvedValueOnce(json(200, { ok: true }))

    expect(await c.login('a@tendoor.dev', 'pw')).toEqual(user)
    await c.api('/analysis/requests', { method: 'POST', body: '{}' })

    const [path, init] = fetchMock.mock.calls[1]
    expect(path).toBe('/api/analysis/requests')
    expect(authHeader(fetchMock.mock.calls[1])).toBe('Bearer T1')
    expect(new Headers(init.headers).get('Content-Type')).toBe('application/json')
    expect(init.credentials).toBe('include')
  })

  it('refreshes once on 401 and repeats the request with the new token', async () => {
    const c = await freshClient()
    fetchMock
      .mockResolvedValueOnce(json(401, { detail: 'expired' }))
      .mockResolvedValueOnce(json(200, { access_token: 'T2', expires_in: 900, user }))
      .mockResolvedValueOnce(json(200, [1, 2]))

    expect(await c.api('/items/1')).toEqual([1, 2])
    expect(fetchMock.mock.calls[1][0]).toBe('/api/auth/refresh')
    expect(authHeader(fetchMock.mock.calls[2])).toBe('Bearer T2')
  })

  it('reports a lost session when refresh fails', async () => {
    const c = await freshClient()
    const lost = vi.fn()
    c.setSessionLostHandler(lost)
    fetchMock.mockResolvedValueOnce(json(401, { detail: 'expired' })).mockResolvedValueOnce(json(401, {}))

    await expect(c.api('/items/1')).rejects.toMatchObject({ status: 401, message: 'expired' })
    expect(lost).toHaveBeenCalledOnce()
  })

  it('does not try to refresh on auth endpoints (wrong password is not an expired session)', async () => {
    const c = await freshClient()
    fetchMock.mockResolvedValueOnce(json(401, { detail: 'Невірний email або пароль' }))
    await expect(c.login('a@tendoor.dev', 'bad')).rejects.toThrow('Невірний email або пароль')
    expect(fetchMock).toHaveBeenCalledOnce()
  })

  it('joins validation messages and falls back for non-JSON errors', async () => {
    const c = await freshClient()
    fetchMock.mockResolvedValueOnce(json(422, { detail: [{ msg: 'поле обовʼязкове' }, { msg: 'надто коротко' }] }))
    await expect(c.api('/x')).rejects.toThrow('поле обовʼязкове; надто коротко')
    fetchMock.mockResolvedValueOnce(new Response('<html>bad gateway</html>', { status: 502 }))
    await expect(c.api('/x')).rejects.toThrow('Помилка 502')
  })

  it('returns undefined for 204', async () => {
    const c = await freshClient()
    fetchMock.mockResolvedValueOnce(new Response(null, { status: 204 }))
    expect(await c.api('/x', { method: 'DELETE' })).toBeUndefined()
  })
})

describe('refreshSession()', () => {
  it('shares one request between parallel callers', async () => {
    const c = await freshClient()
    fetchMock.mockResolvedValueOnce(json(200, { access_token: 'T3', expires_in: 900, user }))
    const [a, b] = await Promise.all([c.refreshSession(), c.refreshSession()])
    expect(a).toEqual(user)
    expect(b).toEqual(user)
    expect(fetchMock).toHaveBeenCalledOnce()
  })
})
