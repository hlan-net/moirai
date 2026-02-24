<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useAuthStore } from '../stores/auth'

// Add types for window globals if needed or use 'any'
declare global {
  interface Window {
    google: any;
    msal: any;
  }
}

const emit = defineEmits(['success'])

const email = ref('')
const password = ref('')
const isLogin = ref(true) // Toggle between Login and Register
const errorMessage = ref('')
const loading = ref(false)
const googleClientId = ref('')
const entraClientId = ref('')
const entraTenantId = ref('')

const authStore = useAuthStore()

const handleAuth = async () => {
  loading.value = true
  errorMessage.value = ''
  
  try {
    if (isLogin.value) {
      const success = await authStore.login(email.value, password.value)
      if (success) {
        emit('success')
        // Only redirect if we are not handling success in parent (e.g. modal)
        // But here we just emit success. The parent decides what to do?
        // Actually, for the standalone page, we want redirect. For modal, we want close.
        // Let's let the parent handle the success.
      } else {
        errorMessage.value = 'Invalid email or password'
      }
    } else {
      // Register (We need to add a register action to store or call API directly)
      // For now, assuming store has register or we call axios directly
      // Let's implement basic register call here for MVP
      const res = await fetch('/api/auth/register', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ email: email.value, password: password.value })
      })
      
      if (res.ok) {
          // Auto login after register
          await authStore.login(email.value, password.value)
          emit('success')
      } else {
          const data = await res.json()
          errorMessage.value = data.message || 'Registration failed'
      }
    }
  } catch (e) {
    console.error("Auth error:", e)
    errorMessage.value = 'An error occurred'
  } finally {
    loading.value = false
  }
}

const fetchAuthConfig = async () => {
    try {
        const res = await fetch('/api/auth/config')
        if (res.ok) {
            const data = await res.json()
            googleClientId.value = data.google_client_id
            entraClientId.value = data.entra_client_id
            entraTenantId.value = data.entra_tenant_id
            // GitHub
            if (data.github_client_id) {
                // We use a specific variable or just use the button if config exists
                 // But wait, we need to pass this to the template
                 // Let's add a ref for it
                 githubClientId.value = data.github_client_id
            }
            
            // Initialize providers if config is present
            if (googleClientId.value) {
                // Check if Google script is loaded, if not load it dynamically? 
                // For now assuming script is in index.html (we should add it)
                // initializeGoogleLogin() 
            }
        }
    } catch (e) {
        console.error("Failed to fetch auth config", e)
    }
}

const githubClientId = ref('')

const handleGoogleLogin = () => {
    if (!googleClientId.value) {
        alert("Google Client ID not configured. Please contact admin.")
        return
    }
    alert(`Google Login not yet fully implemented. Client ID: ${googleClientId.value}`)
    // Actual implementation would trigger GIS flow here
}

const handleEntraLogin = () => {
    if (!entraClientId.value) {
        alert("Microsoft Entra Client ID not configured. Please contact admin.")
        return
    }
    alert(`Entra Login not yet fully implemented. Client ID: ${entraClientId.value}`)
    // Actual implementation would call MSAL loginPopup
}

const handleGithubLogin = () => {
    if (!githubClientId.value) {
        alert("GitHub Client ID not configured. Please contact admin.")
        return
    }
    // Redirect to GitHub
    const redirectUri = globalThis.location.origin + '/login'
    const scope = 'user:email'
    const authUrl = `https://github.com/login/oauth/authorize?client_id=${githubClientId.value}&redirect_uri=${encodeURIComponent(redirectUri)}&scope=${scope}`
    globalThis.location.href = authUrl
}

const checkGithubCallback = async () => {
    const urlParams = new URLSearchParams(globalThis.location.search)
    const code = urlParams.get('code')
    if (code) {
        loading.value = true
        try {
            const success = await authStore.loginWithGithub(code)
            if (success) {
                // Clear query params
                globalThis.history.replaceState({}, document.title, globalThis.location.pathname)
                emit('success')
            } else {
                errorMessage.value = 'GitHub Login Failed'
            }
        } catch (e) {
            console.error(e)
            errorMessage.value = 'GitHub Login Error'
        } finally {
            loading.value = false
        }
    }
}

onMounted(() => {
    fetchAuthConfig()
    checkGithubCallback()
})
</script>

<template>
  <div class="login-card">
    <slot name="header">
      <h1>Moirai</h1>
      <h2>{{ isLogin ? 'Sign In' : 'Create Account' }}</h2>
    </slot>
    
    <div v-if="errorMessage" class="error-alert">{{ errorMessage }}</div>
    
    <form @submit.prevent="handleAuth">
      <div class="form-group">
        <label for="email">Email</label>
        <input type="email" id="email" v-model="email" required />
      </div>
      
      <div class="form-group">
        <label for="password">Password</label>
        <input type="password" id="password" v-model="password" required />
      </div>
      
      <button type="submit" :disabled="loading" class="primary-btn">
        {{ loading ? 'Processing...' : (isLogin ? 'Sign In' : 'Register') }}
      </button>
    </form>
    
    <div class="divider">OR</div>
    
    <div class="social-login">
      <button type="button" class="google-btn" @click="handleGoogleLogin">
        Sign in with Google
      </button>
      <button type="button" class="microsoft-btn" @click="handleEntraLogin">
        Sign in with Microsoft
      </button>
      <button type="button" class="github-btn" @click="handleGithubLogin">
        Sign in with GitHub
      </button>
    </div>
    
    <div class="switch-mode">
      <p v-if="isLogin">
        Don't have an account? <a href="#" @click.prevent="isLogin = false">Register</a>
      </p>
      <p v-else>
        Already have an account? <a href="#" @click.prevent="isLogin = true">Sign In</a>
      </p>
    </div>
  </div>
</template>

<style scoped>
.login-card {
  background: var(--card-bg, white);
  padding: 2rem;
  border-radius: 8px;
  width: 100%;
  max-width: 400px;
  text-align: center;
}

h1 {
  margin-bottom: 0.5rem;
  color: var(--primary-color, #3498db);
}

h2 {
  margin-bottom: 1.5rem;
  font-weight: normal;
  color: var(--text-color);
}

.form-group {
  margin-bottom: 1rem;
  text-align: left;
}

label {
  display: block;
  margin-bottom: 0.5rem;
  font-weight: bold;
}

input {
  width: 100%;
  padding: 0.75rem;
  border: 1px solid var(--border-color, #ddd);
  border-radius: 4px;
  background-color: var(--input-bg, #fff);
  color: var(--input-text, #333);
}

.primary-btn {
  width: 100%;
  padding: 0.75rem;
  background-color: var(--primary-color, #3498db);
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 1rem;
  margin-top: 1rem;
}

.primary-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.divider {
  margin: 1.5rem 0;
  display: flex;
  align-items: center;
  color: var(--text-muted, #777);
}

.divider::before, .divider::after {
  content: "";
  flex: 1;
  border-bottom: 1px solid var(--border-color, #ddd);
}

.divider::before {
  margin-right: 0.5em;
}

.divider::after {
  margin-left: 0.5em;
}

.social-login button {
  width: 100%;
  padding: 0.75rem;
  margin-bottom: 0.5rem;
  border: 1px solid var(--border-color, #ddd);
  border-radius: 4px;
  background-color: var(--card-bg, white);
  cursor: pointer;
  display: flex;
  justify-content: center;
  align-items: center;
  color: var(--text-color);
}

.error-alert {
  background-color: #ffebee;
  color: #c62828;
  padding: 0.75rem;
  border-radius: 4px;
  margin-bottom: 1rem;
}

.switch-mode {
  margin-top: 1.5rem;
  font-size: 0.9rem;
}

a {
  color: var(--primary-color, #3498db);
  text-decoration: none;
}

.github-btn {
  background-color: #24292e;
  color: white !important;
  border-color: #24292e !important;
}
.github-btn:hover {
  background-color: #1a1e22 !important;
}
</style>
