<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useNamespace } from '../composables/useNamespace'

const { currentNamespace, namespaces, initNamespace } = useNamespace()

interface Message {
  role: 'user' | 'assistant'
  content: string
}

const messages = ref<Message[]>([])
const input = ref('')
const loading = ref(false)

onMounted(() => {
    initNamespace()
})

const sendMessage = async () => {
  if (!input.value.trim() || loading.value) return
  
  const userMsg = input.value.trim()
  input.value = ''
  
  messages.value.push({ role: 'user', content: userMsg })
  loading.value = true
  
  try {
    const history = messages.value.slice(0, -1).map(m => ({
      role: m.role,
      content: m.content
    }))
    
    const model = localStorage.getItem('moirai_model') || 'llama3.1'

    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
          message: userMsg, 
          history, 
          model,
          namespace: currentNamespace.value
      })
    })
    
    if (res.ok) {
      const data = await res.json()
      messages.value.push({ role: 'assistant', content: data.response })
    } else {
      messages.value.push({ role: 'assistant', content: `Error: ${res.statusText}` })
    }
  } catch (e) {
    messages.value.push({ role: 'assistant', content: `Error: ${e}` })
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="chat-page">
    <div class="chat-header">
       <select v-model="currentNamespace" class="ns-select">
        <option value="">-- No Context (Global) --</option>
        <option v-for="ns in namespaces" :key="ns" :value="ns">
          {{ ns }}
        </option>
      </select>
    </div>
    <div class="chat-container">
      <div class="messages">
        <div 
          v-for="(msg, idx) in messages" 
          :key="idx" 
          :class="['message', msg.role]"
        >
          <div class="bubble">
            <strong>{{ msg.role === 'user' ? 'You' : 'GenAI' }}:</strong>
            <pre class="msg-content">{{ msg.content }}</pre>
          </div>
        </div>
        <div v-if="loading" class="message assistant">
          <div class="bubble loading">Thinking...</div>
        </div>
      </div>
      
      <div class="input-area">
        <input 
          v-model="input" 
          @keyup.enter="sendMessage" 
          placeholder="Ask Moirai..." 
          :disabled="loading"
        />
        <button @click="sendMessage" :disabled="loading">Send</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chat-page {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 20px;
  overflow: hidden;
}
.chat-header {
    text-align: center;
    margin-bottom: 10px;
}
.ns-select {
  padding: 8px;
  width: 300px;
  border: 1px solid #ccc;
  border-radius: 4px;
}
.chat-container {
  max-width: 800px;
  margin: 0 auto;
  width: 100%;
  display: flex;
  flex-direction: column;
  height: 100%;
  border: 1px solid #ccc;
  border-radius: 8px;
  background: white;
}
.messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 15px;
}
.message {
  display: flex;
}
.message.user {
  justify-content: flex-end;
}
.message.assistant {
  justify-content: flex-start;
}
.bubble {
  padding: 10px 15px;
  border-radius: 8px;
  max-width: 80%;
  word-wrap: break-word;
}
.user .bubble {
  background: #007acc;
  color: white;
}
.assistant .bubble {
  background: #f0f0f0;
  color: #333;
}
.loading {
  font-style: italic;
  color: #888;
}
.msg-content {
  white-space: pre-wrap;
  font-family: inherit;
  margin: 0;
}
.input-area {
  padding: 15px;
  border-top: 1px solid #eee;
  display: flex;
  gap: 10px;
}
input {
  flex: 1;
  padding: 10px;
  border: 1px solid #ddd;
  border-radius: 4px;
}
button {
  padding: 10px 20px;
  background: #007acc;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}
button:disabled {
  background: #ccc;
}
</style>
