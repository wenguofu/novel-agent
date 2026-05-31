import { create } from 'zustand'

interface UIState {
  currentNovel: string | null
  setCurrentNovel: (name: string | null) => void
}

export const useNovelStore = create<UIState>((set) => ({
  currentNovel: null,
  setCurrentNovel: (name) => set({ currentNovel: name }),
}))
