<script setup lang="ts">
import { onMounted } from 'vue'
import { useTheme } from './composables/useTheme'

const { initTheme } = useTheme()

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
        <router-link to="/dashboard" class="nav-link">Dashboard</router-link>
        <router-link to="/chat" class="nav-link">Chat</router-link>
        <router-link to="/settings" class="nav-link">Settings</router-link>
      </div>
    </nav>
    
    <div class="content">
      <router-view v-slot="{ Component }">
        <keep-alive>
          <component :is="Component" msg="Moirai Dashboard" />
        </keep-alive>
      </router-view>
    </div>
  </div>
</template>

<style>
/* Global reset for full height */
body, html, #app {
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
  background-color: #333;
  color: white;
  gap: 10px;
}

.brand {
  font-weight: bold;
  font-size: 1.1rem;
  color: white;
  text-decoration: none;
}

.brand:hover {
  text-decoration: underline;
}

.links {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: center;
  width: 100%;
}

.nav-link {
  color: #ddd;
  text-decoration: none;
  font-weight: 500;
  font-size: 0.9rem;
  padding: 5px 10px;
}

.nav-link:hover, .nav-link.router-link-active {
  color: white;
  text-decoration: underline;
}

.content {
  flex: 1;
  overflow: auto;
  display: flex;
  flex-direction: column;
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
    font-size: 1.2rem;
  }

  .links {
    flex-wrap: nowrap;
    gap: 20px;
    width: auto;
  }

  .nav-link {
    font-size: 1rem;
    padding: 0;
  }
}
</style>