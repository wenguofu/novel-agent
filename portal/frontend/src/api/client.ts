import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'

const BASE_URL = ''

interface RequestOptions {
  method: string
  headers?: Record<string, string>
  body?: string
}

async function request<T = any>(path: string, options: RequestOptions): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...options.headers,
  }

  const resp = await fetch(`${BASE_URL}${path}`, {
    method: options.method,
    headers,
    body: options.body,
  })

  const data = await resp.json()

  if (!resp.ok) {
    throw new Error(data.error || `HTTP ${resp.status}`)
  }

  return data as T
}

export const apiClient = {
  get<T = any>(path: string): Promise<T> {
    return request<T>(path, { method: 'GET' })
  },

  post<T = any>(path: string, body?: unknown): Promise<T> {
    return request<T>(path, {
      method: 'POST',
      body: body ? JSON.stringify(body) : undefined,
    })
  },

  put<T = any>(path: string, body: unknown): Promise<T> {
    return request<T>(path, {
      method: 'PUT',
      body: JSON.stringify(body),
    })
  },

  del<T = any>(path: string): Promise<T> {
    return request<T>(path, { method: 'DELETE' })
  },
}

// ═══════════════════════════════════════════════════════════════════════
// React Query Hooks
// ═══════════════════════════════════════════════════════════════════════

export interface Novel {
  name: string
  title: string
  genre?: string
  subgenre?: string
  total_chapters: number
  total_words: number
  last_chapter?: string
  last_chapter_words?: number
  has_characters?: boolean
  review_count?: number
  volumes?: Array<{
    name: string
    chapter_count: number
    total_words: number
  }>
}

export interface ConfigInfo {
  deepseek_configured: boolean
  deepseek_model: string
  deepseek_api_base: string
  deepseek_key_masked: string
  deepseek_temperature: number
  deepseek_max_tokens: number
  deepseek_top_p: number
}

// Novel list
export function useNovels() {
  return useQuery({
    queryKey: ['novels'],
    queryFn: async () => {
      const data = await apiClient.get<{ success: boolean; novels: Novel[] }>('/api/novels')
      return data.novels || []
    },
  })
}

// Novel detail
export function useNovelDetail(name: string | null) {
  return useQuery({
    queryKey: ['novel', name],
    queryFn: async () => {
      const data = await apiClient.get<any>(`/api/novels/${encodeURIComponent(name!)}`)
      return data.novel || data
    },
    enabled: !!name,
  })
}

// Generate chapter mutation
export function useGenerateChapter(novelName: string | null) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (params: {
      chapter_num: string
      volume?: string
      style?: string
      instructions?: string
      temperature?: number
      max_tokens?: number
    }) =>
      apiClient.post<any>(`/api/novels/${encodeURIComponent(novelName!)}/generate-chapter`, params),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['novel', novelName] })
      qc.invalidateQueries({ queryKey: ['novels'] })
    },
  })
}

// Review chapter mutation
export function useReviewChapter(novelName: string | null) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (params: {
      chapter_ref: string
      volume?: string
      chapter_num?: string
    }) =>
      apiClient.post<any>(`/api/novels/${encodeURIComponent(novelName!)}/review-chapter`, params),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['novel', novelName] })
    },
  })
}

// Optimize chapter mutation
export function useOptimizeChapter(novelName: string | null) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (params: {
      chapter_ref: string
      volume?: string
      chapter_num?: string
      review_text?: string
      script_issues?: string
    }) =>
      apiClient.post<any>(`/api/novels/${encodeURIComponent(novelName!)}/optimize-chapter`, params),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['novel', novelName] })
    },
  })
}

// Config
export function useConfig() {
  return useQuery({
    queryKey: ['config'],
    queryFn: async () => {
      return apiClient.get<ConfigInfo>('/api/config')
    },
  })
}

export function useSaveConfig() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (config: Record<string, string>) =>
      apiClient.post<any>('/api/config/save', config),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['config'] })
    },
  })
}
