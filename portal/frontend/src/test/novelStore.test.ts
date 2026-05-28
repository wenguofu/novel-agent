import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockFetch = vi.fn()
vi.stubGlobal('fetch', mockFetch)

// We import after mocking fetch
let novelStore: any

// Dynamic import to ensure fetch is mocked before store loads
beforeEach(async () => {
  mockFetch.mockReset()
  vi.resetModules()
  const mod = await import('../stores/novelStore')
  novelStore = mod.useNovelStore
})

describe('novelStore', () => {
  it('starts with null current novel', () => {
    const state = novelStore.getState()
    expect(state.currentNovel).toBeNull()
    expect(state.novels).toEqual([])
  })

  it('setCurrentNovel updates current novel', () => {
    novelStore.getState().setCurrentNovel('test-novel')
    expect(novelStore.getState().currentNovel).toBe('test-novel')
  })

  it('fetchNovels loads novel list from API', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        novels: [{ name: 'novel1', title: '测试小说', total_chapters: 10 }],
      }),
    })

    await novelStore.getState().fetchNovels()

    expect(mockFetch).toHaveBeenCalledWith('/api/novels')
    const novels = novelStore.getState().novels
    expect(novels).toHaveLength(1)
    expect(novels[0].name).toBe('novel1')
  })
})
