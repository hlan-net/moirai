import { createRouter, createWebHashHistory } from 'vue-router'
import MainPage from './components/MainPage.vue'
import SettingsPage from './components/SettingsPage.vue'
import ChatPage from './components/ChatPage.vue'
import StreamPage from './components/StreamPage.vue'

const routes = [
  { path: '/', redirect: '/stream' },
  { path: '/stream', component: StreamPage, name: 'Stream' },
  { path: '/dashboard', component: MainPage, name: 'Dashboard' },
  { path: '/chat', component: ChatPage, name: 'Chat' },
  { path: '/settings', component: SettingsPage, name: 'Settings' },
]

const router = createRouter({
  history: createWebHashHistory(), 
  routes,
})

export default router