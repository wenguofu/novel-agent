import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock fetch globally
const mockFetch = vi.fn()
vi.stubGlobal('fetch', mockFetch)

import { apiClient } from '../api/client'

describe('apiClient', () => {
  beforeEach(() => {
    mockFetch.mockReset()
  })

  it('makes GET requests with correct URL', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ novels: [] }),
    })

    const result = await apiClient.get('/api/novels')

    expect(mockFetch).toHaveBeenCalledWith('/api/novels', expect.objectContaining({
      method: 'GET',
    }))
    expect(result).toEqual({ novels: [] })
  })

  it('makes POST requests with JSON body', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ success: true }),
    })

    const result = await apiClient.post('/api/novels/create', { name: 'test' })

    expect(mockFetch).toHaveBeenCalledWith('/api/novels/create', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ name: 'test' }),
    }))
    expect(result).toEqual({ success: true })
  })

  it('throws on non-ok response', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 404,
      json: async () => ({ error: 'not found' }),
    })

    await expect(apiClient.get('/api/missing')).rejects.toThrow('not found')
  })
})
