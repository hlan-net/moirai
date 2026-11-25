import { createRouter, createWebHashHistory } from 'vue-router'
import { useAuthStore } from './stores/auth'
import SettingsPage from './components/SettingsPage.vue'
import StreamPage from './components/StreamPage.vue'
import LoginPage from './components/LoginPage.vue'

// The UI is the Stream page, Login and Settings (#375). The views that were
// removed keep their paths as redirects, so old bookmarks and links land on
// the stream instead of an empty page.
const REMOVED_PATHS = [
  '/dashboard',
  '/lifespan',
  '/chat',
  '/agents',
  '/sessions',
  '/sessions/:id',
  '/mythology',
]

const routes = [
  { path: '/', component: StreamPage, name: 'Stream' }, // Stream is public-ish (or handled by guard)
  { path: '/stream', component: StreamPage, name: 'StreamExplicit' }, // Explicit /stream route for navigation
  { path: '/login', component: LoginPage, name: 'Login' },
  { path: '/settings', component: SettingsPage, name: 'Settings', meta: { requiresAuth: true } },
  ...REMOVED_PATHS.map((path) => ({ path, redirect: '/' })),
  { path: '/:pathMatch(.*)*', redirect: '/' },
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
