import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Review } from '../pages/Review'

const mockNovels = vi.hoisted(() => [
  { name: 'novel1', title: '测试小说', total_chapters: 42 },
])

vi.mock('../stores/novelStore', () => {
  const store = { novels: mockNovels, currentNovel: 'novel1', loading: false, fetchNovels: vi.fn(), setCurrentNovel: vi.fn() }
  return { useNovelStore: (s?: any) => (s ? s(store) : store) }
})

describe('Review', () => {
  it('renders title and volume/chapter inputs', () => {
    render(<MemoryRouter><Review /></MemoryRouter>)
    expect(screen.getByText('审稿台')).toBeInTheDocument()
    // Volume and chapter inputs should be present
    const inputs = screen.getAllByRole('spinbutton')
    expect(inputs.length).toBeGreaterThanOrEqual(2)
  })

  it('has run review button', () => {
    render(<MemoryRouter><Review /></MemoryRouter>)
    expect(screen.getByText('运行审稿')).toBeInTheDocument()
  })
})
