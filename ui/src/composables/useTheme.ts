import { ref } from 'vue'

export type Theme = 'light' | 'dark' | 'auto'

const theme = ref<Theme>('auto')

type ThemeUpdateOptions = {
  persist?: boolean
}

export function useTheme() {
  const prefersDarkQuery = globalThis.matchMedia('(prefers-color-scheme: dark)')
  const systemPrefersDark = ref(prefersDarkQuery.matches)

  const resolveTheme = () => {
    const isDark = theme.value === 'dark' || (theme.value === 'auto' && systemPrefersDark.value)
    return isDark ? 'dark' : 'light'
  }

  const applyTheme = () => {
    const root = document.documentElement
    const resolved = resolveTheme()

    if (resolved === 'dark') {
      root.classList.add('dark-theme')
      root.classList.remove('light-theme')
    } else {
      root.classList.add('light-theme')
      root.classList.remove('dark-theme')
    }
  }

  const setTheme = (newTheme: Theme, options: ThemeUpdateOptions = {}) => {
    theme.value = newTheme
    if (options.persist !== false) {
      localStorage.setItem('moirai_theme', newTheme)
    }
    applyTheme()
  }

  const initTheme = () => {
    const saved = localStorage.getItem('moirai_theme') as Theme
    if (saved) {
      theme.value = saved
    }
    applyTheme()

    // Listen for system changes if in auto mode
    prefersDarkQuery.addEventListener('change', (event) => {
      systemPrefersDark.value = event.matches
      if (theme.value === 'auto') {
        applyTheme()
      }
    })
  }

  return {
    theme,
    systemPrefersDark,
    resolveTheme,
    setTheme,
    initTheme
  }
}
