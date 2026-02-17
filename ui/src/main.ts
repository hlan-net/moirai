import { createApp } from 'vue'
import { createPinia } from 'pinia'
import './style.css'
import App from './App.vue'
import router from './router'
import axios from 'axios'

// Configure axios defaults
axios.defaults.withCredentials = true
// Add interceptor to use token from store if available
axios.interceptors.request.use(config => {
  const authData = localStorage.getItem('moirai_auth')
  if (authData) {
    try {
      const { token } = JSON.parse(authData)
      if (token) {
        config.headers.Authorization = `Bearer ${token}`
      }
    } catch (e) {
      console.error('Error parsing auth data for axios interceptor', e)
    }
  }
  return config
})

const pinia = createPinia()
const app = createApp(App)

app.use(pinia)
app.use(router)
app.mount('#app')