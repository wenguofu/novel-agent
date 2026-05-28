import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Dashboard } from '../pages/Dashboard'

const mockNovels = vi.hoisted(() => [
  { name: 'novel1', title: '测试小说', total_chapters: 42, total_words: 120000 },
  { name: 'novel2', title: '第二本书', total_chapters: 15, total_words: 45000 },
])

// Mock zustand with selector support
vi.mock('../stores/novelStore', () => {
  const store = {
    novels: mockNovels,
    currentNovel: null,
    loading: false,
    fetchNovels: vi.fn(),
    setCurrentNovel: vi.fn(),
  }
  return {
    useNovelStore: (selector?: any) => (selector ? selector(store) : store),
  }
})

describe('Dashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders welcome message', () => {
    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>
    )

    expect(screen.getByText('欢迎使用 NovelForge')).toBeInTheDocument()
  })

  it('displays novel count in stats', () => {
    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>
    )

    expect(screen.getByText('2')).toBeInTheDocument()
    expect(screen.getByText('小说数量')).toBeInTheDocument()
  })

  it('lists novels with action buttons', () => {
    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>
    )

    expect(screen.getByText('测试小说')).toBeInTheDocument()
    expect(screen.getByText('第二本书')).toBeInTheDocument()
    expect(screen.getByText(/42 章/)).toBeInTheDocument()
    expect(screen.getByText(/15 章/)).toBeInTheDocument()
  })
})
