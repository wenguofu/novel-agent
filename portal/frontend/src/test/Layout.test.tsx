import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Layout } from '../components/Layout'

const mockNovels = vi.hoisted(() => [
  { name: 'novel1', title: '测试小说', total_chapters: 42 },
])

const mockStore = vi.hoisted(() => ({
  novels: mockNovels,
  currentNovel: null as string | null,
  loading: false,
  fetchNovels: vi.fn(),
  setCurrentNovel: vi.fn(),
}))

vi.mock('../stores/novelStore', () => ({
  useNovelStore: (selector?: any) => (selector ? selector(mockStore) : mockStore),
}))

describe('Layout', () => {
  beforeEach(() => {
    mockStore.currentNovel = null
  })

  it('renders sidebar with global navigation items (no novel)', () => {
    render(
      <MemoryRouter>
        <Layout>content</Layout>
      </MemoryRouter>
    )

    expect(screen.getByText('NovelForge')).toBeInTheDocument()
    expect(screen.getByText('控制台')).toBeInTheDocument()
    expect(screen.getByText('新建小说')).toBeInTheDocument()
    expect(screen.getByText('搜索')).toBeInTheDocument()
    expect(screen.getByText('配置')).toBeInTheDocument()
    // Novel-specific items should NOT be visible without novel selected
    expect(screen.queryByText('写作')).not.toBeInTheDocument()
  })

  it('shows novel workspace items when novel selected', () => {
    mockStore.currentNovel = 'novel1'

    render(
      <MemoryRouter>
        <Layout>content</Layout>
      </MemoryRouter>
    )

    expect(screen.getByText('写作')).toBeInTheDocument()
    expect(screen.getByText('章节')).toBeInTheDocument()
    expect(screen.getByText('大纲')).toBeInTheDocument()
    expect(screen.getByText('人物')).toBeInTheDocument()
  })

  it('renders children in main content area', () => {
    render(
      <MemoryRouter>
        <Layout>
          <div data-testid="child">hello world</div>
        </Layout>
      </MemoryRouter>
    )

    expect(screen.getByTestId('child')).toBeInTheDocument()
    expect(screen.getByTestId('child')).toHaveTextContent('hello world')
  })

  it('highlights active global nav item based on current route', () => {
    render(
      <MemoryRouter initialEntries={['/search']}>
        <Layout>search page</Layout>
      </MemoryRouter>
    )

    const searchItem = screen.getByText('搜索').closest('li')
    expect(searchItem).toHaveClass('ant-menu-item-selected')
  })

  it('highlights active novel nav item when novel selected', () => {
    mockStore.currentNovel = 'novel1'

    render(
      <MemoryRouter initialEntries={['/writing']}>
        <Layout>writing page</Layout>
      </MemoryRouter>
    )

    const writingItem = screen.getByText('写作').closest('li')
    expect(writingItem).toHaveClass('ant-menu-item-selected')
  })

  it('shows guide when navigating to novel page without novel', () => {
    render(
      <MemoryRouter initialEntries={['/writing']}>
        <Layout>fallback</Layout>
      </MemoryRouter>
    )

    expect(screen.getByText('请先选择一部小说')).toBeInTheDocument()
  })
})
