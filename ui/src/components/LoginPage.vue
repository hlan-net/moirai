<script setup lang="ts">
import { useRouter } from 'vue-router'
import LoginForm from './LoginForm.vue'

const router = useRouter()

const handleSuccess = () => {
  router.push('/')
}
</script>

<template>
  <div class="login-container">
    <LoginForm @success="handleSuccess" class="login-page-card" />
  </div>
</template>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background-color: var(--bg-color, #f4f4f9);
  color: var(--text-color, #333);
}

.login-page-card {
  box-shadow: 0 4px 6px rgba(0,0,0,0.1);
}
</style>
