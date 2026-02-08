<script setup lang="ts">
import LoginForm from './LoginForm.vue'

const emit = defineEmits(['close', 'success'])

const handleClose = () => {
    emit('close')
}

const handleSuccess = () => {
    emit('success')
    emit('close')
}
</script>

<template>
  <div class="modal-overlay" @click.self="handleClose">
    <div class="modal-content" role="dialog" aria-modal="true">
      <button class="close-btn" @click="handleClose" aria-label="Close modal">&times;</button>
      <LoginForm @success="handleSuccess">
        <template #header>
            <h1>Login Required</h1>
            <p class="subtitle">Please sign in to continue</p>
        </template>
      </LoginForm>
    </div>
  </div>
</template>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
}

.modal-content {
  background: var(--card-bg);
  border-radius: 8px;
  width: 100%;
  max-width: 450px;
  position: relative;
  /* LoginForm handles its own padding, but we might want a bit wrapper padding if needed. 
     LoginForm has padding: 2rem. */
  max-height: 90vh;
  overflow-y: auto;
}

.close-btn {
  position: absolute;
  top: 10px;
  right: 15px;
  background: none;
  border: none;
  font-size: 24px;
  cursor: pointer;
  color: var(--text-color);
  z-index: 10;
}

.subtitle {
    text-align: center;
    color: var(--text-color);
    opacity: 0.8;
    margin-bottom: 20px;
}
</style>
