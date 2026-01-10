import { createRouter, createWebHashHistory } from 'vue-router'
import MainPage from './components/MainPage.vue'
import SettingsPage from './components/SettingsPage.vue'
import ChatPage from './components/ChatPage.vue'
import HistoryPage from './components/HistoryPage.vue'
import ChatHistoryPage from './components/ChatHistoryPage.vue'
import ChatHistoryViewPage from './components/ChatHistoryViewPage.vue'

const routes = [
  { path: '/', component: HistoryPage, name: 'History' },
  { path: '/dashboard', component: MainPage, name: 'Dashboard' },
  { path: '/chat', component: ChatPage, name: 'Chat' },
  { path: '/settings', component: SettingsPage, name: 'Settings' },
  { path: '/chat/history', component: ChatHistoryPage, name: 'ChatHistory' },
  { path: '/chat/history/:id', component: ChatHistoryViewPage, name: 'ChatHistoryView' },
]

const router = createRouter({
  history: createWebHashHistory(), 
  routes,
})

export default router