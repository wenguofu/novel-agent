import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render } from '@testing-library/react'
import { ConfigPage } from '../pages/ConfigPage'

// Default mock store: no saved config, fetchConfig resolves immediately.
const mockConfigStore = vi.hoisted(() => ({
  deepseekConfig: {} as Record<string, any>,
  configured: false,
  fetchConfig: vi.fn().mockResolvedValue(undefined),
  saveConfig: vi.fn().mockResolvedValue({ success: true, deepseek_configured: false }),
  testConfig: vi.fn().mockResolvedValue(true),
}))

// useConfigStore is a zustand-style hook: callable with a selector AND has
// .getState()/.setState() methods. The real ConfigPage uses both patterns.
const useConfigStoreMock = vi.hoisted(() => {
  const fn = (selector?: any) =>
    selector ? selector(mockConfigStore) : mockConfigStore
  fn.getState = () => mockConfigStore
  fn.setState = (partial: any) => Object.assign(mockConfigStore, partial)
  fn.subscribe = () => () => {}
  return fn
})

vi.mock('../stores/configStore', () => ({
  useConfigStore: useConfigStoreMock,
}))

describe('ConfigPage — model selection (V3 default)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockConfigStore.deepseekConfig = {}
  })

  it('renders MiniMax V3 as the default selected model', () => {
    const { container } = render(<ConfigPage />)
    // The model selector is a <Select> with the value 'MiniMax-M3' and label
    // 'MiniMax V3'. Antd v6 renders the selected label text in the DOM.
    const text = container.textContent || ''
    expect(text).toContain('MiniMax V3')
  })

  it('does NOT render "M2.7" anywhere on the page', () => {
    const { container } = render(<ConfigPage />)
    // Grep the entire rendered tree for "M2.7" — should be zero matches.
    expect(container.textContent).not.toContain('M2.7')
  })

  it('initializes max_tokens to 65536 (matches backend DEFAULT_MAX_TOKENS)', () => {
    const { container } = render(<ConfigPage />)
    // antd InputNumber renders an <input role="spinbutton"> with the current value.
    const spinbuttons = container.querySelectorAll('input[role="spinbutton"]') as NodeListOf<HTMLInputElement>
    const values = Array.from(spinbuttons).map((el) => el.value)
    expect(values).toContain('65536')
    // And must NOT default to 8192 (the old value)
    expect(values).not.toContain('8192')
  })

  it('labels the MiniMax API base endpoint as "MiniMax V3 (Anthropic兼容)"', () => {
    const { container } = render(<ConfigPage />)
    const text = container.textContent || ''
    // The MiniMax API base label must include "MiniMax V3" and "Anthropic兼容"
    // and must NOT include "M2.7"
    expect(text).toContain('MiniMax V3 (Anthropic兼容)')
    expect(text).not.toContain('M2.7')
  })
})
