import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from 'axios'
import router from '../router'

export const useAuthStore = defineStore('auth', () => {
    const token = ref<string | null>(localStorage.getItem('token'))
    const user = ref<any>(null)
    const isAuthenticated = computed(() => !!token.value)

    // Configure axios defaults
    if (token.value) {
        axios.defaults.headers.common['Authorization'] = `Bearer ${token.value}`
    }

    async function login(email: string, password: string) {
        try {
            const response = await axios.post('/api/auth/login', { email, password })
            const data = response.data
            setToken(data.access_token)
            user.value = {
                id: data.user_id,
                email: data.email,
                role: data.role
            }
            return true
        } catch (error) {
            console.error('Login failed', error)
            return false
        }
    }

    async function loginWithGoogle(googleToken: string) {
        try {
            const response = await axios.post('/api/auth/login/google', { token: googleToken })
            const data = response.data
            setToken(data.access_token)
            user.value = {
                id: data.user_id,
                email: data.email,
                role: data.role
            }
            return true
        } catch (error) {
            console.error('Google login failed', error)
            return false
        }
    }

    async function loginWithEntra(entraToken: string) {
        try {
            const response = await axios.post('/api/auth/login/entra', { token: entraToken })
            const data = response.data
            setToken(data.access_token)
            user.value = {
                id: data.user_id,
                email: data.email,
                role: data.role
            }
            return true
        } catch (error) {
            console.error('Entra login failed', error)
            return false
        }
    }

    async function loginWithGithub(code: string) {
        try {
            const response = await axios.post('/api/auth/login/github', { code })
            const data = response.data
            setToken(data.access_token)
            user.value = {
                id: data.user_id,
                email: data.email,
                role: data.role
            }
            return true
        } catch (error) {
            console.error('GitHub login failed', error)
            return false
        }
    }

    function setToken(newToken: string) {
        token.value = newToken
        localStorage.setItem('token', newToken)
        axios.defaults.headers.common['Authorization'] = `Bearer ${newToken}`
    }

    function logout() {
        token.value = null
        user.value = null
        localStorage.removeItem('token')
        delete axios.defaults.headers.common['Authorization']
        router.push('/login')
    }

    async function fetchUser() {
        if (!token.value) return
        try {
            const response = await axios.get('/api/auth/me')
            user.value = response.data
        } catch (error) {
            console.error('Fetch user failed', error)
            logout()
        }
    }

    // Initialize
    if (token.value) {
        fetchUser()
    }

    return {
        token,
        user,
        isAuthenticated,
        login,
        loginWithGoogle,
        loginWithEntra,
        loginWithGithub,
        logout,
        fetchUser
    }
})
