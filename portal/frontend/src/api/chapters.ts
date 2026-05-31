// API functions for context building and generation
import { apiClient } from './client'

interface ContextRequest {
  novel_name: string
  volume: string
  chapter: number | string
  style?: string
}

export async function buildContext(params: ContextRequest): Promise<string> {
  const data = await apiClient.post<{ system_prompt: string }>('/api/context/build', {
    novel_name: params.novel_name,
    volume: params.volume,
    chapter_num: params.chapter,
    style: params.style || '',
  })
  return data.system_prompt || ''
}

export async function fetchNovelFiles(novel: string, files: string[]): Promise<Record<string, string>> {
  const results = await Promise.all(
    files.map(async (f) => {
      try {
        const data = await apiClient.get<{ content: string }>(
          `/api/novels/${encodeURIComponent(novel)}/file?path=${encodeURIComponent(f)}`
        )
        return { name: f, content: data.content || '' }
      } catch {
        return { name: f, content: '' }
      }
    })
  )
  return Object.fromEntries(results.map((r) => [r.name, r.content]))
}

export async function saveChapter(
  novel: string,
  chapterRef: string,
  content: string,
  volume: string,
  chapterNum: number
) {
  return apiClient.post(`/api/novels/${encodeURIComponent(novel)}/chapters/${chapterRef}/edit`, {
    content,
    volume,
    chapter_num: chapterNum,
  })
}
