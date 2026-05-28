import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Writing } from '../pages/Writing'

const mockNovels = vi.hoisted(() => [
  { name: 'novel1', title: '测试小说', total_chapters: 42, total_words: 120000 },
])

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

describe('Writing', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders page title and volume/chapter inputs', () => {
    render(
      <MemoryRouter>
        <Writing />
      </MemoryRouter>
    )

    expect(screen.getByText('写作台')).toBeInTheDocument()
    // Volume and chapter spinbuttons should be present
    const inputs = screen.getAllByRole('spinbutton')
    expect(inputs.length).toBeGreaterThanOrEqual(2)
  })

  it('has generate button', () => {
    render(
      <MemoryRouter>
        <Writing />
      </MemoryRouter>
    )

    expect(screen.getByText('生成单章')).toBeInTheDocument()
  })
})
