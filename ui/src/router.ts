import { createRouter, createWebHashHistory } from 'vue-router'
import { useAuthStore } from './stores/auth'
import MainPage from './components/MainPage.vue'
import SettingsPage from './components/SettingsPage.vue'
import ChatPage from './components/ChatPage.vue'
import StreamPage from './components/StreamPage.vue'
import LoginPage from './components/LoginPage.vue'

const routes = [
  { path: '/', component: StreamPage, name: 'Stream' }, // Stream is public-ish (or handled by guard)
  { path: '/login', component: LoginPage, name: 'Login' },
  { path: '/dashboard', component: MainPage, name: 'Dashboard', meta: { requiresAuth: true } },
  { path: '/chat', component: ChatPage, name: 'Chat', meta: { requiresAuth: true } },
  { path: '/settings', component: SettingsPage, name: 'Settings', meta: { requiresAuth: true } },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

router.beforeEach(async (to, _from, next) => {
  const authStore = useAuthStore()
  await authStore.initialize()

  // Check if route requires auth
  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    next('/login')
  } else {
    next()
  }
})

export default router
