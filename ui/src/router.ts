import { createRouter, createWebHashHistory } from 'vue-router'
import { useAuthStore } from './stores/auth'
import MainPage from './components/MainPage.vue'
import SettingsPage from './components/SettingsPage.vue'
import ChatPage from './components/ChatPage.vue'
import StreamPage from './components/StreamPage.vue'
import LoginPage from './components/LoginPage.vue'
import AgentManagementPage from './components/AgentManagementPage.vue'
import LifespanView from './components/LifespanView.vue'
import MythologyPage from './components/MythologyPage.vue'
import SessionsPage from './components/SessionsPage.vue'

const routes = [
  { path: '/', component: StreamPage, name: 'Stream' }, // Stream is public-ish (or handled by guard)
  { path: '/mythology', component: MythologyPage, name: 'Mythology' },
  { path: '/stream', component: StreamPage, name: 'StreamExplicit' }, // Explicit /stream route for navigation
  { path: '/login', component: LoginPage, name: 'Login' },
  { path: '/dashboard', component: MainPage, name: 'Dashboard', meta: { requiresAuth: true } },
  { path: '/lifespan', component: LifespanView, name: 'Lifespan', meta: { requiresAuth: true } },
  { path: '/chat', component: ChatPage, name: 'Chat', meta: { requiresAuth: true } },
  { path: '/settings', component: SettingsPage, name: 'Settings', meta: { requiresAuth: true } },
  {
    path: '/agents',
    component: AgentManagementPage,
    name: 'AgentManagement',
    meta: { requiresAuth: true },
  },
  { path: '/sessions', component: SessionsPage, name: 'Sessions', meta: { requiresAuth: true } },
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
