import { useAuthStore } from '../stores/auth'
import router from '../router'

type AuthFetchInit = RequestInit & { requireAuth?: boolean }

const redirectToLogin = () => {
  try {
    const authStore = useAuthStore()
    authStore.logout()
  } catch (error) {
    console.warn('Auth store unavailable, redirecting to login', error)
    localStorage.removeItem('token')
    router.push('/login')
  }
}

export const authFetch = async (
  input: RequestInfo | URL,
  init: AuthFetchInit = {}
) => {
  const headers = new Headers(init.headers || {})
  const token = localStorage.getItem('token')

  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  const response = await fetch(input, { ...init, headers })

  if (init.requireAuth !== false && response.status === 401) {
    redirectToLogin()
  }

  return response
}
