import { ref } from 'vue'

export type Theme = 'light' | 'dark' | 'auto'

const theme = ref<Theme>('auto')

export function useTheme() {
  
  const applyTheme = () => {
    const root = document.documentElement
    const isDark = theme.value === 'dark' || 
      (theme.value === 'auto' && window.matchMedia('(prefers-color-scheme: dark)').matches)

    if (isDark) {
      root.classList.add('dark-theme')
      root.classList.remove('light-theme')
    } else {
      root.classList.add('light-theme')
      root.classList.remove('dark-theme')
    }
  }

  const setTheme = (newTheme: Theme) => {
    theme.value = newTheme
    localStorage.setItem('moirai_theme', newTheme)
    applyTheme()
  }

  const initTheme = () => {
    const saved = localStorage.getItem('moirai_theme') as Theme
    if (saved) {
      theme.value = saved
    }
    applyTheme()

    // Listen for system changes if in auto mode
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
      if (theme.value === 'auto') {
        applyTheme()
      }
    })
  }

  return {
    theme,
    setTheme,
    initTheme
  }
}
