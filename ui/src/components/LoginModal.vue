<script setup lang="ts">
import { ref, onMounted } from 'vue'
import LoginForm from './LoginForm.vue'

const emit = defineEmits(['close', 'success'])
const dialogRef = ref<HTMLDialogElement | null>(null)

const handleClose = () => {
    emit('close')
}

const handleSuccess = () => {
    emit('success')
    emit('close')
}

onMounted(() => {
  if (dialogRef.value) {
    dialogRef.value.showModal()
  }
})
</script>

<template>
  <div class="modal-overlay" @click.self="handleClose">
    <dialog ref="dialogRef" class="modal-content" @close="handleClose">
      <button class="close-btn" @click="handleClose" aria-label="Close modal">&times;</button>
      <LoginForm @success="handleSuccess">
        <template #header>
            <h1>Login Required</h1>
            <p class="subtitle">Please sign in to continue</p>
        </template>
      </LoginForm>
    </dialog>
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
  color: var(--text-color);
  border-radius: 8px;
  border: 1px solid var(--border-color);
  width: 100%;
  max-width: 450px;
  position: relative;
  max-height: 90vh;
  overflow-y: auto;
  padding: 0;
  margin: auto;
}

.modal-content::backdrop {
  background: transparent; /* Use overlay instead */
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
