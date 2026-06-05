import { create } from 'zustand'
import type { UserSettings, PortfolioSummary } from '../lib/types'

interface AppStore {
  settings: UserSettings | null
  portfolio: PortfolioSummary | null
  setSettings: (s: UserSettings | null) => void
  setPortfolio: (p: PortfolioSummary | null) => void
}

export const useAppStore = create<AppStore>((set) => ({
  settings: null,
  portfolio: null,
  setSettings: (settings) => set({ settings }),
  setPortfolio: (portfolio) => set({ portfolio }),
}))
