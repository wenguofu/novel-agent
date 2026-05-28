import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Chapters } from '../pages/Chapters'

const mockNovels = vi.hoisted(() => [
  { name: 'novel1', title: '测试小说', total_chapters: 42, total_words: 120000 },
])

vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
  ok: true,
  json: async () => ({
    success: true,
    novel: {
      volumes: [
        { name: 'vol-01', chapters: [
          { name: 'ch-0001', words: 3200 },
          { name: 'ch-0002', words: 2800 },
        ]},
        { name: 'vol-02', chapters: [
          { name: 'ch-0003', words: 3100 },
        ]},
      ],
    },
  }),
}))

vi.mock('../stores/novelStore', () => {
  const store = { novels: mockNovels, currentNovel: 'novel1', loading: false, fetchNovels: vi.fn(), setCurrentNovel: vi.fn() }
  return { useNovelStore: (s?: any) => (s ? s(store) : store) }
})

describe('Chapters', () => {
  it('renders page title and novel selector', async () => {
    render(<MemoryRouter><Chapters /></MemoryRouter>)
    await waitFor(() => {
      expect(screen.getByText('章节浏览')).toBeInTheDocument()
    })
  })

  it('shows chapter list grouped by volume', async () => {
    render(<MemoryRouter><Chapters /></MemoryRouter>)
    await waitFor(() => {
      expect(screen.getByText('第1章')).toBeInTheDocument()
      expect(screen.getByText('第2章')).toBeInTheDocument()
      expect(screen.getByText('第3章')).toBeInTheDocument()
    })
  })

  it('has search input', async () => {
    render(<MemoryRouter><Chapters /></MemoryRouter>)
    await waitFor(() => {
      expect(screen.getByPlaceholderText('搜索章节...')).toBeInTheDocument()
    })
  })
})
