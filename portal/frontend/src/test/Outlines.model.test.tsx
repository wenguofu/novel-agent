import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock the config store so we can control what model the page reads.
const mockConfigStore = vi.hoisted(() => ({
  deepseekConfig: { deepseek_model: 'MiniMax-M3' } as Record<string, any>,
  configured: true,
  fetchConfig: vi.fn().mockResolvedValue(undefined),
  saveConfig: vi.fn(),
  testConfig: vi.fn(),
}))

const mockNovels = vi.hoisted(() => [
  { name: 'novel1', title: '测试小说', total_chapters: 42, total_words: 120000 },
])

// Build the zustand-style hook mock via hoisted factory so .getState is available.
vi.mock('../stores/configStore', () => {
  const fn = (selector?: any) =>
    selector ? selector(mockConfigStore) : mockConfigStore
  ;(fn as any).getState = () => mockConfigStore
  ;(fn as any).setState = (partial: any) => Object.assign(mockConfigStore, partial)
  return { useConfigStore: fn }
})

vi.mock('../stores/novelStore', () => {
  const store = {
    novels: mockNovels,
    currentNovel: 'novel1',
    loading: false,
    fetchNovels: vi.fn(),
    setCurrentNovel: vi.fn(),
  }
  return {
    useNovelStore: (selector?: any) => (selector ? selector(store) : store),
  }
})

// Mock fetch globally so we can assert what /api/ai/chat receives.
const mockFetch = vi.fn()
vi.stubGlobal('fetch', mockFetch)

import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Outlines } from '../pages/Outlines'

describe('Outlines — model sourcing from useConfigStore', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockConfigStore.deepseekConfig = { deepseek_model: 'MiniMax-M3' }

    // Default mock for fetch: load returns content, AI chat returns a YAML response.
    mockFetch.mockImplementation(async (url: string) => {
      if (typeof url === 'string' && url.includes('/outline/')) {
        return { ok: true, json: async () => ({ content: '' }) }
      }
      if (typeof url === 'string' && url.includes('/api/ai/chat')) {
        return {
          ok: true,
          json: async () => ({ success: true, content: 'volume: 1\nchapters: []' }),
        }
      }
      return { ok: true, json: async () => ({}) }
    })
  })

  it('handleAIGenerate posts model from useConfigStore (NOT a hardcoded string)', async () => {
    render(
      <MemoryRouter>
        <Outlines />
      </MemoryRouter>
    )

    // Find the AI-generate button. The page labels it "AI 生成大纲" or similar.
    // Use a flexible matcher: any button whose text includes "AI" and "生成".
    const buttons = screen.getAllByRole('button')
    const aiBtn = buttons.find((b) => /AI.*生成|生成.*AI/.test(b.textContent || ''))
    expect(aiBtn).toBeDefined()

    // Click to trigger handleAIGenerate.
    aiBtn!.click()

    // Wait for the fetch to /api/ai/chat to be called.
    await waitFor(() => {
      const calls = mockFetch.mock.calls
      const chatCalls = calls.filter((c) => typeof c[0] === 'string' && c[0].includes('/api/ai/chat'))
      expect(chatCalls.length).toBeGreaterThan(0)
    })

    // Inspect the most recent /api/ai/chat call.
    const calls = mockFetch.mock.calls
    const chatCall = [...calls].reverse().find((c) => typeof c[0] === 'string' && c[0].includes('/api/ai/chat'))
    expect(chatCall).toBeDefined()
    const body = JSON.parse((chatCall![1] as RequestInit).body as string)

    // The model MUST be the value from useConfigStore, not a hardcoded "MiniMax-M2.7".
    expect(body.model).toBe('MiniMax-M3')
    expect(body.model).not.toBe('MiniMax-M2.7')
  })

  it('reflects a different configured model in the POST body', async () => {
    // Switch the store to a different model value.
    mockConfigStore.deepseekConfig = { deepseek_model: 'deepseek-v4-pro' }

    render(
      <MemoryRouter>
        <Outlines />
      </MemoryRouter>
    )

    const buttons = screen.getAllByRole('button')
    const aiBtn = buttons.find((b) => /AI.*生成|生成.*AI/.test(b.textContent || ''))
    expect(aiBtn).toBeDefined()
    aiBtn!.click()

    await waitFor(() => {
      const calls = mockFetch.mock.calls
      const chatCalls = calls.filter((c) => typeof c[0] === 'string' && c[0].includes('/api/ai/chat'))
      expect(chatCalls.length).toBeGreaterThan(0)
    })

    const calls = mockFetch.mock.calls
    const chatCall = [...calls].reverse().find((c) => typeof c[0] === 'string' && c[0].includes('/api/ai/chat'))
    const body = JSON.parse((chatCall![1] as RequestInit).body as string)
    expect(body.model).toBe('deepseek-v4-pro')
  })
})
