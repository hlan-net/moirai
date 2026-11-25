<script setup lang="ts">
// The Stream page's choices in one menu (#344): sections (several at once),
// density, grouping, theme and the RSS link for the current view. A menu
// button with a role="menu" panel; the sections are menuitemcheckbox, the
// view choices menuitemradio. Arrow keys, Home and End move the focus; Escape
// closes and returns it to the button; a press outside closes the menu.
import { computed, nextTick, onUnmounted, ref, useId, watch } from 'vue'
import { SECTIONS, type SectionKey } from '../utils/streamSections'

type GroupMode = 'feed' | 'time'

const props = defineProps<{
  showTheme: boolean
  themeLabel: string
  rssUrl: string
}>()

const sections = defineModel<SectionKey[]>('sections', { required: true })
const highDensity = defineModel<boolean>('highDensity', { required: true })
const groupMode = defineModel<GroupMode>('groupMode', { required: true })

const emit = defineEmits<{ toggleTheme: [] }>()

const menuId = `stream-menu-${useId()}`
const open = ref(false)
const root = ref<HTMLElement | null>(null)
const button = ref<HTMLButtonElement | null>(null)
const panel = ref<HTMLElement | null>(null)

const themeText = computed(() => `Theme: ${props.themeLabel}`)

const items = (): HTMLElement[] =>
  panel.value ? Array.from(panel.value.querySelectorAll<HTMLElement>('[role^="menuitem"]')) : []

const focusItem = (index: number) => {
  const list = items()
  if (list.length === 0) return
  const wrapped = ((index % list.length) + list.length) % list.length
  list[wrapped]?.focus()
}

const openMenu = async (focus: 'first' | 'last' = 'first') => {
  open.value = true
  await nextTick()
  focusItem(focus === 'first' ? 0 : -1)
}

const closeMenu = (returnFocus = true) => {
  if (!open.value) return
  open.value = false
  if (returnFocus) button.value?.focus()
}

const toggleMenu = () => {
  if (open.value) closeMenu()
  else void openMenu()
}

const onButtonKeydown = (event: KeyboardEvent) => {
  if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
    event.preventDefault()
    void openMenu(event.key === 'ArrowDown' ? 'first' : 'last')
  }
}

const onMenuKeydown = (event: KeyboardEvent) => {
  const list = items()
  const current = list.indexOf(document.activeElement as HTMLElement)
  switch (event.key) {
    case 'ArrowDown':
      event.preventDefault()
      focusItem(current + 1)
      break
    case 'ArrowUp':
      event.preventDefault()
      focusItem(current - 1)
      break
    case 'Home':
      event.preventDefault()
      focusItem(0)
      break
    case 'End':
      event.preventDefault()
      focusItem(-1)
      break
    case 'Escape':
      event.preventDefault()
      closeMenu()
      break
    case 'Tab':
      closeMenu(false)
      break
  }
}

// mousedown, not click: a press that starts outside closes the menu even if
// it ends inside, and a text selection dragged out of the menu does not.
const onDocumentMousedown = (event: MouseEvent) => {
  if (root.value && !root.value.contains(event.target as Node)) closeMenu(false)
}

watch(open, (isOpen) => {
  if (isOpen) document.addEventListener('mousedown', onDocumentMousedown)
  else document.removeEventListener('mousedown', onDocumentMousedown)
})

onUnmounted(() => document.removeEventListener('mousedown', onDocumentMousedown))

const isChecked = (key: SectionKey) => sections.value.includes(key)

const toggleSection = (key: SectionKey) => {
  sections.value = isChecked(key)
    ? sections.value.filter((k) => k !== key)
    : SECTIONS.map((s) => s.key).filter((k) => k === key || sections.value.includes(k))
}

const chooseTheme = () => {
  emit('toggleTheme')
}
</script>

<template>
  <div ref="root" class="stream-menu">
    <button
      ref="button"
      type="button"
      class="menu-btn"
      aria-haspopup="menu"
      :aria-expanded="open"
      :aria-controls="menuId"
      aria-label="Stream options"
      title="Sections and view options"
      @click="toggleMenu"
      @keydown="onButtonKeydown"
    >
      <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
        <path d="M3 6h18v2H3V6zm0 5h18v2H3v-2zm0 5h18v2H3v-2z" />
      </svg>
    </button>

    <div
      v-show="open"
      :id="menuId"
      ref="panel"
      class="menu-panel"
      role="menu"
      aria-label="Stream options"
      @keydown="onMenuKeydown"
    >
      <div role="group" :aria-labelledby="`${menuId}-sections`">
        <div :id="`${menuId}-sections`" class="menu-heading">Sections</div>
        <button
          v-for="section in SECTIONS"
          :key="section.key"
          type="button"
          role="menuitemcheckbox"
          class="menu-item"
          tabindex="-1"
          :aria-checked="isChecked(section.key)"
          :data-section="section.key"
          @click="toggleSection(section.key)"
        >
          <span class="mark" aria-hidden="true">{{ isChecked(section.key) ? '☑' : '☐' }}</span>
          {{ section.label }}
        </button>
      </div>

      <div role="separator" class="menu-separator"></div>

      <div role="group" :aria-labelledby="`${menuId}-view`">
        <div :id="`${menuId}-view`" class="menu-heading">View</div>
        <button
          type="button"
          role="menuitemradio"
          class="menu-item"
          tabindex="-1"
          :aria-checked="highDensity"
          @click="highDensity = true"
        >
          <span class="mark" aria-hidden="true">{{ highDensity ? '◉' : '○' }}</span>
          Compact
        </button>
        <button
          type="button"
          role="menuitemradio"
          class="menu-item"
          tabindex="-1"
          :aria-checked="!highDensity"
          @click="highDensity = false"
        >
          <span class="mark" aria-hidden="true">{{ highDensity ? '○' : '◉' }}</span>
          Expanded
        </button>
      </div>

      <div role="group" aria-label="Grouping">
        <button
          type="button"
          role="menuitemradio"
          class="menu-item"
          tabindex="-1"
          :aria-checked="groupMode === 'feed'"
          @click="groupMode = 'feed'"
        >
          <span class="mark" aria-hidden="true">{{ groupMode === 'feed' ? '◉' : '○' }}</span>
          By feed
        </button>
        <button
          type="button"
          role="menuitemradio"
          class="menu-item"
          tabindex="-1"
          :aria-checked="groupMode === 'time'"
          @click="groupMode = 'time'"
        >
          <span class="mark" aria-hidden="true">{{ groupMode === 'time' ? '◉' : '○' }}</span>
          By time
        </button>
      </div>

      <div role="separator" class="menu-separator"></div>

      <button
        v-if="showTheme"
        type="button"
        role="menuitem"
        class="menu-item"
        tabindex="-1"
        @click="chooseTheme"
      >
        <span class="mark" aria-hidden="true">◐</span>
        {{ themeText }}
      </button>
      <a
        role="menuitem"
        class="menu-item"
        tabindex="-1"
        :href="rssUrl"
        target="_blank"
        rel="noopener"
        @click="closeMenu()"
      >
        <span class="mark rss-mark" aria-hidden="true">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
            <path
              d="M6.18 15.64a2.18 2.18 0 0 1 2.18 2.18C8.36 19 7.38 20 6.18 20A2.18 2.18 0 0 1 4 17.82a2.18 2.18 0 0 1 2.18-2.18M4 4.44A15.56 15.56 0 0 1 19.56 20h-2.83A12.73 12.73 0 0 0 4 7.27V4.44m0 5.66a9.9 9.9 0 0 1 9.9 9.9h-2.83A7.07 7.07 0 0 0 4 12.93V10.1z"
            />
          </svg>
        </span>
        RSS for this view
      </a>
    </div>
  </div>
</template>

<style scoped>
.stream-menu {
  position: relative;
}

.menu-btn {
  background: transparent;
  border: 1px solid var(--border-color);
  color: var(--text-color);
  padding: 6px 10px;
  border-radius: 4px;
  cursor: pointer;
  display: flex;
  align-items: center;
  box-shadow: none;
  transition: all 0.2s;
}

.menu-btn:hover,
.menu-btn[aria-expanded='true'] {
  background: var(--button-bg);
  border-color: var(--primary-color);
}

.menu-panel {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  z-index: 1500;
  min-width: 220px;
  padding: 6px 0;
  background: var(--card-bg);
  color: var(--text-color);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
}

.menu-heading {
  padding: 6px 14px 2px;
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  opacity: 0.7;
}

.menu-item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 6px 14px;
  background: transparent;
  border: none;
  border-radius: 0;
  color: var(--text-color);
  font-size: 0.9rem;
  text-align: left;
  font-weight: 400;
  text-decoration: none;
  cursor: pointer;
  box-shadow: none;
}

.menu-item:hover,
.menu-item:focus,
.menu-item:focus-visible {
  background: var(--button-bg);
  box-shadow: none;
  outline: none;
}

.menu-item:focus-visible {
  box-shadow: inset 3px 0 0 var(--primary-color);
}

.mark {
  display: inline-flex;
  justify-content: center;
  width: 1.2em;
}

.rss-mark {
  color: #ee802f;
}

.menu-separator {
  height: 1px;
  margin: 6px 0;
  background: var(--border-color);
}
</style>
