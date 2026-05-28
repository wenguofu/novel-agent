import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { NewBook } from '../pages/NewBook'

vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
  ok: true,
  json: async () => ({ success: true, steps: [], genres: {} }),
}))

describe('NewBook', () => {
  it('renders creation wizard title', async () => {
    render(<MemoryRouter><NewBook /></MemoryRouter>)
    await waitFor(() => {
      expect(screen.getByText('新建小说')).toBeInTheDocument()
    })
  })

  it('has name input as first step', async () => {
    render(<MemoryRouter><NewBook /></MemoryRouter>)
    await waitFor(() => {
      expect(screen.getByPlaceholderText('请输入小说名称')).toBeInTheDocument()
    })
  })

  it('has genre selector', async () => {
    render(<MemoryRouter><NewBook /></MemoryRouter>)
    await waitFor(() => {
      expect(screen.getByText('类型')).toBeInTheDocument()
    })
  })
})
