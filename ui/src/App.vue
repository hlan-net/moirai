<script setup lang="ts">
</script>

<template>
  <div class="app-container">
    <nav class="main-nav">
      <div class="brand">Moirai</div>
      <div class="links">
        <router-link to="/" class="nav-link">Dashboard</router-link>
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
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
</style>