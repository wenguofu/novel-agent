import { create } from 'zustand'

interface DeepSeekConfig {
  api_key?: string
  api_base?: string
  model?: string
  temperature?: number
  max_tokens?: number
  top_p?: number
}

interface ConfigState {
  deepseekConfig: DeepSeekConfig
  configured: boolean
  fetchConfig: () => Promise<void>
  saveConfig: (config: DeepSeekConfig) => Promise<void>
  testConfig: () => Promise<boolean>
}

export const useConfigStore = create<ConfigState>((set) => ({
  deepseekConfig: {},
  configured: false,

  fetchConfig: async () => {
    try {
      const resp = await fetch('/api/config')
      const data = await resp.json()
      set({
        deepseekConfig: data,
        configured: !!(data.api_key || data.api_base),
      })
    } catch {
      // ignore
    }
  },

  saveConfig: async (config) => {
    await fetch('/api/config/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
    })
    set({ deepseekConfig: config, configured: !!(config.api_key || config.api_base) })
  },

  testConfig: async () => {
    try {
      const resp = await fetch('/api/config/test', { method: 'POST' })
      const data = await resp.json()
      return data.success === true
    } catch {
      return false
    }
  },
}))
