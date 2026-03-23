# Settings Store Refactoring Plan

## Problem Statement

localStorage is accessed directly in 39+ places across the frontend, leading to:
- ❌ Synchronization issues between components
- ❌ Stale data when settings change
- ❌ No reactivity - components don't know when settings update
- ❌ Duplicate code for reading/writing settings
- ❌ Hard to maintain and debug

## Solution: Centralized Reactive Settings Store

Created `ui/src/stores/settings.ts` - A Pinia store that:
- ✅ Single source of truth for all settings
- ✅ Automatic localStorage sync via watchers
- ✅ Reactive - all components update instantly
- ✅ Type-safe with TypeScript
- ✅ Clean API for getting/setting values

## Store API

```typescript
import { useSettingsStore } from '@/stores/settings'

const settingsStore = useSettingsStore()

// Read settings (reactive)
settingsStore.llmEndpoint        // 'ollama' | 'openai' | 'gemini'
settingsStore.ollamaModel        // 'llama3.2:3b'
settingsStore.openaiModel        // 'gpt-4-turbo'
settingsStore.geminiModel        // 'gemini-1.5-pro'
settingsStore.getCurrentModel()  // Returns current model based on provider

// Update settings (auto-syncs to localStorage)
settingsStore.llmEndpoint = 'openai'
settingsStore.setCurrentModel('gpt-4-turbo')

// Load from backend
await settingsStore.loadFromBackend(backendSettings)

// Save to backend
const payload = await settingsStore.saveToBackend()
```

## Migration Steps

### Phase 1: Core Components (HIGH PRIORITY) ✅ DONE

1. ✅ Created `stores/settings.ts`
2. ⏳ Update `ChatPage.vue` to use store
3. ⏳ Update `ContextChatModal.vue` to use store
4. ⏳ Update `SettingsPage.vue` to use store

### Phase 2: Remove StorageEvent Workarounds

Current implementation uses `StorageEvent` to broadcast changes.
With Pinia store, this is no longer needed because:
- Pinia provides built-in reactivity
- All components share the same store instance
- Changes propagate automatically

**Remove from:**
- `ChatPage.vue` - Remove `handleStorageChange()` and event listeners
- `ContextChatModal.vue` - Remove `handleStorageChange()` and event listeners
- `SettingsPage.vue` - Remove `window.dispatchEvent(new StorageEvent...)`

### Phase 3: Other Components

4. Update `useTheme.ts` to use store
5. Update any other components using localStorage

## Files to Modify

### High Priority (Affects Model Selection)
- [x] `stores/settings.ts` - Created
- [ ] `components/ChatPage.vue` - 20+ localStorage calls
- [ ] `components/ContextChatModal.vue` - 5+ localStorage calls  
- [ ] `components/SettingsPage.vue` - 10+ localStorage calls

### Medium Priority
- [ ] `composables/useTheme.ts` - Theme settings
- [ ] `utils/authFetch.ts` - Token storage (keep separate for security)

### Low Priority (Already Working)
- [ ] `stores/auth.ts` - Token storage (keep as-is)
- [ ] `main.ts` - Minimal usage

## Benefits After Migration

### 1. Instant Reactivity
```typescript
// Before: Manual localStorage + events
localStorage.setItem('moirai_model', 'llama3.2:3b')
window.dispatchEvent(new StorageEvent('storage', {...}))
// Component must listen and reload

// After: Just update store
settingsStore.setCurrentModel('llama3.2:3b')
// All components update automatically!
```

### 2. Type Safety
```typescript
// Before: Strings everywhere
const model = localStorage.getItem('moirai_model') || 'default'
// What if key is wrong? No error!

// After: TypeScript knows all fields
settingsStore.ollamaModel  // ✓ Type-safe
settingsStore.olamaModel   // ✗ TypeScript error!
```

### 3. Computed Values
```typescript
// Before: Logic in every component
const getCurrentModel = () => {
  const endpoint = localStorage.getItem('moirai_llm_endpoint')
  if (endpoint === 'openai') {
    return localStorage.getItem('moirai_openai_model')
  }
  // ...duplicated everywhere
}

// After: Once in the store
settingsStore.getCurrentModel()  // Clean!
```

### 4. Easier Testing
```typescript
// Before: Mock localStorage
global.localStorage = { getItem: jest.fn(), ... }

// After: Mock store
const mockStore = createPinia()
// Much cleaner!
```

## Implementation Example: ChatPage.vue

### Before (Current)
```typescript
const currentLlmEndpoint = ref('ollama')
const currentModel = ref('llama3.1:latest')

const loadSettings = () => {
  currentLlmEndpoint.value = localStorage.getItem('moirai_llm_endpoint') || 'ollama'
  const settingsKey = modelSettingsMap[currentLlmEndpoint.value] || 'moirai_model'
  currentModel.value = localStorage.getItem(settingsKey) || defaultModel
}

const updateModel = (value: string) => {
  currentModel.value = value
  const settingsKey = modelSettingsMap[currentLlmEndpoint.value] || 'moirai_model'
  localStorage.setItem(settingsKey, value)
  saveUserSetting(settingsKey, value)
}

// Listen for storage events...
window.addEventListener('storage', handleStorageChange)
```

### After (Proposed)
```typescript
import { useSettingsStore } from '@/stores/settings'

const settingsStore = useSettingsStore()

// Read values - automatically reactive!
const currentLlmEndpoint = computed(() => settingsStore.llmEndpoint)
const currentModel = computed(() => settingsStore.getCurrentModel())

// Update values - automatically syncs!
const updateModel = (value: string) => {
  settingsStore.setCurrentModel(value)
  // That's it! No localStorage, no events, no sync code
}

// No event listeners needed!
```

**Result:** 50+ lines reduced to 10 lines, fully reactive, type-safe!

## Testing Plan

1. ✅ Verify store persists to localStorage
2. ✅ Verify watchers trigger on changes
3. ⏳ Test ChatPage model selection
4. ⏳ Test ContextChatModal uses correct model
5. ⏳ Test SettingsPage saves correctly
6. ⏳ Test multi-tab synchronization (Pinia + localStorage)

## Rollout Strategy

### Option A: Big Bang (Risky)
- Refactor all files at once
- High risk of breaking everything
- **Not recommended**

### Option B: Gradual Migration (Recommended) ✅
1. ✅ Create store alongside existing code
2. Migrate ChatPage first (most critical)
3. Test thoroughly
4. Migrate ContextChatModal
5. Test article actions
6. Migrate SettingsPage
7. Remove old StorageEvent code
8. Clean up unused functions

### Option C: Parallel Systems (Safest but Complex)
- Keep localStorage AND store in sync
- Gradually migrate components
- Remove localStorage last
- **Too complex for our use case**

## Current Status

- ✅ Store created (`stores/settings.ts`)
- ⏳ ChatPage migration in progress
- ⏳ Testing required
- ⏳ Documentation needed

## Next Steps

1. Complete ChatPage refactoring
2. Test model selection thoroughly
3. Complete ContextChatModal refactoring
4. Test article-to-issue creation
5. Complete SettingsPage refactoring
6. Remove StorageEvent workarounds
7. Update this document with results

## Notes

- Keep `stores/auth.ts` separate - auth tokens need special handling
- Theme store might be merged into settings store later
- Consider adding settings validation in store
- Consider adding settings migration for schema changes
