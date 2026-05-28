import { create } from 'zustand'

interface Novel {
  name: string
  title: string
  genre?: string
  subgenre?: string
  total_chapters: number
  total_words: number
  last_chapter?: string
}

interface NovelState {
  currentNovel: string | null
  novels: Novel[]
  novelDetail: Novel | null
  loading: boolean
  setCurrentNovel: (name: string | null) => void
  fetchNovels: () => Promise<void>
  fetchNovelDetail: (name: string) => Promise<void>
}

export const useNovelStore = create<NovelState>((set) => ({
  currentNovel: null,
  novels: [],
  novelDetail: null,
  loading: false,

  setCurrentNovel: (name) => set({ currentNovel: name }),

  fetchNovels: async () => {
    set({ loading: true })
    try {
      const resp = await fetch('/api/novels')
      const data = await resp.json()
      set({ novels: data.novels || [], loading: false })
    } catch {
      set({ loading: false })
    }
  },

  fetchNovelDetail: async (name) => {
    set({ loading: true })
    try {
      const resp = await fetch(`/api/novels/${name}`)
      const data = await resp.json()
      set({ novelDetail: data, loading: false })
    } catch {
      set({ loading: false })
    }
  },
}))
