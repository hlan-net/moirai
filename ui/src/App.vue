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
.app-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
}
.main-nav {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 20px;
  background-color: #333;
  color: white;
}
.brand {
  font-weight: bold;
  font-size: 1.2rem;
  color: white;
  text-decoration: none;
}
.brand:hover {
  text-decoration: underline;
}
.links {
  display: flex;
  gap: 20px;
}
.nav-link {
  color: #ddd;
  text-decoration: none;
  font-weight: 500;
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
</style>