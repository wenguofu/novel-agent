import { create } from 'zustand'

interface AIConfig {
  api_key?: string
  api_base?: string
  model?: string
  temperature?: number
  max_tokens?: number
  top_p?: number
}

interface ConfigState {
  deepseekConfig: any
  configured: boolean
  fetchConfig: () => Promise<void>
  saveConfig: (config: AIConfig) => Promise<void>
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
        configured: data.deepseek_configured || data.deepseek_key_saved,
      })
    } catch {
      // ignore
    }
  },

  saveConfig: async (config) => {
    const resp = await fetch('/api/config/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
    })
    const data = await resp.json()
    set({
      deepseekConfig: { ...config, ...data },
      configured: data.deepseek_configured,
    })
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
