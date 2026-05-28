import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { WorldBuilding } from '../pages/WorldBuilding'

const mockNovels = vi.hoisted(() => [
  { name: 'novel1', title: '测试小说', total_chapters: 42 },
])

// Stub fetch to prevent unhandled URL errors in jsdom
vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
  ok: true,
  json: async () => ({ world_building: [] }),
}))

vi.mock('../stores/novelStore', () => {
  const store = { novels: mockNovels, currentNovel: 'novel1', loading: false, fetchNovels: vi.fn(), setCurrentNovel: vi.fn() }
  return { useNovelStore: (s?: any) => (s ? s(store) : store) }
})

describe('WorldBuilding', () => {
  it('renders page title', async () => {
    render(<MemoryRouter><WorldBuilding /></MemoryRouter>)
    await waitFor(() => {
      expect(screen.getByText('世界观管理')).toBeInTheDocument()
    })
  })

  it('has add button', async () => {
    render(<MemoryRouter><WorldBuilding /></MemoryRouter>)
    await waitFor(() => {
      expect(screen.getByText('添加条目')).toBeInTheDocument()
    })
  })
})
