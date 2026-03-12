<script setup lang="ts">
import { onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useTheme } from './composables/useTheme'
import { useAuthStore } from './stores/auth'
import ContextChatModal from './components/ContextChatModal.vue'

const { initTheme } = useTheme()
const authStore = useAuthStore()
const router = useRouter()

const isAuthenticated = computed(() => authStore.isAuthenticated)

const handleLogout = () => {
  authStore.logout()
  router.push('/login')
}

onMounted(() => {
  initTheme()
})
</script>

<template>
  <div class="app-container">
    <nav class="main-nav">
      <a href="https://github.com/hlan-net/moirai" target="_blank" class="brand">Moirai</a>
      <div class="links">
        <router-link to="/stream" class="nav-link">Stream</router-link>
        <template v-if="isAuthenticated">
          <router-link to="/dashboard" class="nav-link">Dashboard</router-link>
          <router-link to="/lifespan" class="nav-link">Lifespan</router-link>
          <router-link to="/chat" class="nav-link">Chat</router-link>
          <router-link to="/settings" class="nav-link">Settings</router-link>
          <router-link to="/agents" class="nav-link">Agents</router-link>
          <a href="#" @click.prevent="handleLogout" class="nav-link logout-link">Logout</a>
        </template>
        <template v-else>
          <router-link to="/login" class="nav-link">Login</router-link>
        </template>
      </div>
    </nav>

    <div class="content">
      <router-view v-slot="{ Component }">
        <keep-alive>
          <component :is="Component" msg="Moirai Dashboard" />
        </keep-alive>
      </router-view>
    </div>

    <ContextChatModal />
  </div>
</template>

<style>
/* Global reset for full height */
body,
html,
#app {
  margin: 0;
  padding: 0;
  height: 100%;
}
</style>

<style scoped>
/* Mobile-first navigation */
.app-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
}

.main-nav {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 10px;
  background-color: var(--card-bg); /* Using card background for navigation */
  color: var(--text-color);
  gap: 10px;
  box-shadow: 0 2px 5px rgba(0, 0, 0, 0.2); /* Add shadow for depth */
}

.brand {
  font-weight: bold;
  font-size: 1.2rem; /* Slightly larger brand font */
  color: white;
  text-decoration: none;
}

.brand:hover {
  text-decoration: none;
  opacity: 0.8;
}

.links {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: center;
  width: 100%;
}

.nav-link {
  color: var(--text-color);
  text-decoration: none;
  font-weight: bold;
  font-size: 0.95rem; /* Slightly larger nav links */
  padding: 5px 10px;
  border-radius: 4px;
  transition:
    background-color 0.2s,
    color 0.2s;
}

.nav-link:hover {
  opacity: 0.8;
  text-decoration: none;
}

.nav-link.router-link-active {
  color: white;
  background-color: rgba(0, 0, 0, 0.2);
  text-decoration: none;
}

.content {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

/* Tablet and up: horizontal navigation */
@media (min-width: 768px) {
  .main-nav {
    flex-direction: row;
    justify-content: space-between;
    padding: 10px 20px;
    gap: 0;
  }

  .brand {
    font-size: 1.3rem;
  }

  .links {
    flex-wrap: nowrap;
    gap: 20px;
    width: auto;
  }

  .nav-link {
    font-size: 1rem;
    padding: 5px 10px;
    background-color: transparent; /* Remove background for horizontal nav */
  }

  .nav-link:hover {
    opacity: 0.8;
    text-decoration: none;
  }

  .nav-link.router-link-active {
    color: white;
    background-color: rgba(0, 0, 0, 0.3);
    text-decoration: none;
  }
}
</style>
