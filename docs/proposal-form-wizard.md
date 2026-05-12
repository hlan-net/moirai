# Proposal: Traditional Form-Based Issue Wizard

**Status:** 🔴 Not yet in roadmap
**Priority:** Medium (UX/Accessibility improvement)
**Effort:** 8-12 hours
**Target:** v0.7.1 or later

---

## Problem Statement

**Current Implementation (v0.6.0):**
- Issue raising happens via **chat interface** (`ContextChatModal.vue`)
- LLM generates 3 clarifying questions conversationally
- User types answers in chat
- Works well for some users, but:
  - ❌ Not intuitive for users unfamiliar with AI chat
  - ❌ Less discoverable (button leads to chat, not obvious modal)
  - ❌ Hard to review answers before submitting
  - ❌ No progress indicator (which step are you on?)
  - ❌ Difficult for accessibility/screen readers

**User Request:**
> "Can we have a traditional wizard, not a chat?"

**Use Cases:**
- Enterprise users familiar with standard forms
- Accessibility-first organizations
- Users who prefer structured input over conversational UX
- Mobile users (chat can feel cramped)

---

## Proposed Solution: Multi-Step Form Wizard

### Design

```
┌─────────────────────────────────────────┐
│  Issue Creation Wizard                  │
├─────────────────────────────────────────┤
│  Step 1 of 4                            │
│  ████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░    │ (Progress bar)
├─────────────────────────────────────────┤
│                                         │
│  What's the main topic?                 │
│  ┌─────────────────────────────────┐   │
│  │ [ Type or select from tags... ] │   │
│  └─────────────────────────────────┘   │
│                                         │
│  Related articles: 3                    │
│  ☐ Article 1: "..."                    │
│  ☑ Article 2: "..." (already selected)  │
│  ☐ Article 3: "..."                    │
│                                         │
├─────────────────────────────────────────┤
│  [Back] [Cancel]              [Next →]  │
└─────────────────────────────────────────┘
```

### User Flow

**Step 1: Core Information**
- Topic/Title field (prefilled from article)
- Add/remove related articles
- Optional: custom summary

**Step 2: Context & Impact**
- Who should care? (Dropdown: Customers, Team, Industry, Everyone)
- Priority level (Low/Medium/High)
- Category tags (Compliance, Product, Security, etc.)

**Step 3: Action Items**
- Suggested action field
- Owner assignment (optional)
- Due date (optional)

**Step 4: Review & Confirm**
- Show full issue preview
- Edit previous steps link
- Confirm to create

---

## Implementation Details

### File Structure

**New Files:**
```
ui/src/components/
  ├── IssueWizard.vue          (Main wizard component)
  ├── IssueWizardStep1.vue     (Core info)
  ├── IssueWizardStep2.vue     (Context & impact)
  ├── IssueWizardStep3.vue     (Action items)
  └── IssueWizardStep4.vue     (Review)

ui/src/stores/
  └── issueWizard.ts           (Wizard state management)
```

**Modified Files:**
- `ui/src/components/ArticleDetail.vue` — Add wizard button
- `ui/src/components/ArticleList.vue` — Add quick-raise button

### Step 1: Core Information

```vue
<template>
  <div class="wizard-step">
    <h2>What's the main topic?</h2>

    <div class="form-group">
      <label>Issue Title *</label>
      <input
        v-model="form.title"
        placeholder="e.g., Supply chain disruption in Southeast Asia"
        @input="suggestTopics"
      />
      <div v-if="suggestedTopics" class="suggestions">
        <span v-for="topic in suggestedTopics" @click="selectTopic(topic)">
          {{ topic }}
        </span>
      </div>
    </div>

    <div class="form-group">
      <label>Related Articles</label>
      <div class="article-selector">
        <div v-for="article in availableArticles" :key="article._id" class="checkbox">
          <input
            type="checkbox"
            v-model="form.articleIds"
            :value="article._id"
          />
          <span>{{ article.title }}</span>
          <span class="meta">{{ article.source }} • {{ article.publishedDate }}</span>
        </div>
      </div>
    </div>

    <div class="form-group">
      <label>Initial Summary (Optional)</label>
      <textarea
        v-model="form.summary"
        placeholder="What's happening? Why does it matter?"
        rows="4"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useIssueWizardStore } from '@/stores/issueWizard'

const store = useIssueWizardStore()
const form = ref({
  title: '',
  articleIds: [],
  summary: ''
})

const suggestedTopics = ref<string[]>([])

// Auto-suggest topics from selected articles
function suggestTopics() {
  const articles = form.value.articleIds.map(id =>
    availableArticles.value.find(a => a._id === id)
  )
  // Call LLM to suggest topics
}
</script>

<style scoped>
.wizard-step {
  padding: 2rem;
  max-width: 600px;
}

.form-group {
  margin-bottom: 1.5rem;
}

label {
  display: block;
  margin-bottom: 0.5rem;
  font-weight: 500;
}

input, textarea {
  width: 100%;
  padding: 0.75rem;
  border: 1px solid var(--border-color);
  border-radius: 4px;
  font-family: inherit;
}

.suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 0.5rem;
}

.suggestions span {
  padding: 0.25rem 0.75rem;
  background: var(--tag-bg);
  cursor: pointer;
  border-radius: 20px;
  font-size: 0.85rem;
}

.article-selector {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  max-height: 300px;
  overflow-y: auto;
}

.checkbox {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  padding: 0.5rem;
}

.meta {
  font-size: 0.8rem;
  color: var(--text-secondary);
}
</style>
```

### Step 4: Review

```vue
<template>
  <div class="wizard-step review">
    <h2>Review Your Issue</h2>

    <div class="preview-card">
      <h3>{{ form.title }}</h3>

      <div class="field">
        <strong>Summary:</strong>
        <p>{{ form.summary }}</p>
      </div>

      <div class="field">
        <strong>Impact:</strong>
        <p>{{ form.impact }}</p>
      </div>

      <div class="field">
        <strong>Priority:</strong>
        <span class="badge" :class="form.priority">{{ form.priority }}</span>
      </div>

      <div class="field">
        <strong>Articles ({{ form.articleIds.length }}):</strong>
        <ul>
          <li v-for="id in form.articleIds" :key="id">
            {{ getArticleTitle(id) }}
          </li>
        </ul>
      </div>

      <div class="field" v-if="form.action">
        <strong>Suggested Action:</strong>
        <p>{{ form.action }}</p>
      </div>
    </div>

    <p class="help-text">
      You can edit any section by clicking [Edit] below, or create the issue and refine it later.
    </p>

    <div class="edit-links">
      <a href="#" @click.prevent="goToStep(1)">Edit topic</a>
      <a href="#" @click.prevent="goToStep(2)">Edit context</a>
      <a href="#" @click.prevent="goToStep(3)">Edit actions</a>
    </div>
  </div>
</template>

<style scoped>
.review {
  max-width: 700px;
}

.preview-card {
  background: var(--card-bg);
  padding: 1.5rem;
  border-radius: 8px;
  margin-bottom: 1.5rem;
  border: 1px solid var(--border-color);
}

.preview-card h3 {
  margin-top: 0;
  font-size: 1.4rem;
}

.field {
  margin-bottom: 1.5rem;
  padding-bottom: 1.5rem;
  border-bottom: 1px solid var(--border-color);
}

.field:last-child {
  border-bottom: none;
}

.badge {
  display: inline-block;
  padding: 0.25rem 0.75rem;
  border-radius: 20px;
  font-size: 0.85rem;
  font-weight: 500;
}

.badge.high {
  background: #fee;
  color: #c00;
}

.badge.medium {
  background: #fef3cd;
  color: #856404;
}

.badge.low {
  background: #d4edda;
  color: #155724;
}

.edit-links {
  display: flex;
  gap: 1rem;
}

.edit-links a {
  color: var(--link-color);
  text-decoration: none;
}

.edit-links a:hover {
  text-decoration: underline;
}
</style>
```

### State Management (Pinia)

```typescript
// ui/src/stores/issueWizard.ts
import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useIssueWizardStore = defineStore('issueWizard', () => {
  const currentStep = ref(1)
  const totalSteps = ref(4)

  const form = ref({
    title: '',
    summary: '',
    articleIds: [] as string[],
    impact: '',
    priority: 'medium',
    category: '',
    action: '',
    owner: '',
    dueDate: '',
  })

  const goToStep = (step: number) => {
    if (step >= 1 && step <= totalSteps.value) {
      currentStep.value = step
    }
  }

  const nextStep = () => {
    if (currentStep.value < totalSteps.value) {
      currentStep.value++
    }
  }

  const previousStep = () => {
    if (currentStep.value > 1) {
      currentStep.value--
    }
  }

  const resetWizard = () => {
    currentStep.value = 1
    form.value = {
      title: '',
      summary: '',
      articleIds: [],
      impact: '',
      priority: 'medium',
      category: '',
      action: '',
      owner: '',
      dueDate: '',
    }
  }

  return {
    currentStep,
    totalSteps,
    form,
    goToStep,
    nextStep,
    previousStep,
    resetWizard,
  }
})
```

---

## Comparison: Chat vs Form Wizard

| Aspect | Chat Wizard | Form Wizard | Best For |
|--------|------------|------------|----------|
| **Learning curve** | Steep (requires AI comfort) | Shallow (familiar UI) | First-time users |
| **Speed** | Fast (just answer) | Medium (more fields) | Quick entry |
| **Discoverability** | Low (inside chat) | High (obvious modal) | New users |
| **Accessibility** | Poor (chat semantics) | Good (form labels) | WCAG compliance |
| **Mobile** | Cramped | Better | Mobile users |
| **AI-guided** | Yes (LLM asks questions) | No (static form) | Lazy users |
| **Customization** | Hard (chat logic) | Easy (form config) | Admins |

---

## Recommendation: Hybrid Approach

**Keep both!** Why choose?

```
┌──────────────────────────────┐
│   Raise Issue                │
├──────────────────────────────┤
│ Choose your style:           │
│                              │
│ [ ] Chat Wizard              │
│     (Ask me questions)       │
│                              │
│ [✓] Form Wizard              │
│     (I'll fill fields)       │
│                              │
│ [  ] Quick Create            │
│     (Just title + summary)   │
└──────────────────────────────┘
```

This way:
- **Power users** use the form (faster, more control)
- **New users** use the chat (guided, friendly)
- **Busy users** use quick create (minimal fields)

---

## User Preference Persistence

```typescript
// Save user's preference
localStorage.setItem('issueWizardStyle', 'form') // or 'chat'

// Next time they raise an issue, use their preference
```

---

## Implementation Plan

### Phase 1: Core Form Wizard (8-10 hours)
- [x] IssueWizard.vue main component
- [x] Step 1-4 components
- [x] Pinia store
- [x] API integration
- [x] Basic styling

### Phase 2: UX Polish (2-3 hours)
- [x] Progress bar animations
- [x] Step validation (disable Next if required fields empty)
- [x] Auto-save to prevent data loss
- [x] Keyboard navigation (Tab, Enter, Esc)

### Phase 3: Optional Hybrid Toggle (2-4 hours)
- [x] Let users choose chat vs form
- [x] Remember preference
- [x] Show "Quick Create" option

---

## Testing

```typescript
// tests/issueWizard.spec.ts
describe('IssueWizard', () => {
  it('should navigate between steps', () => {
    const store = useIssueWizardStore()
    expect(store.currentStep).toBe(1)

    store.nextStep()
    expect(store.currentStep).toBe(2)
  })

  it('should prevent going past step 4', () => {
    const store = useIssueWizardStore()
    store.currentStep = 4

    store.nextStep()
    expect(store.currentStep).toBe(4) // stays at 4
  })

  it('should validate required fields', () => {
    // Title required
    // At least 1 article
  })

  it('should submit issue on completion', () => {
    // POST /api/issues with form data
  })
})
```

---

## Migration Path

1. **v0.7.1:** Add form wizard alongside chat wizard
2. **v0.7.2:** Add user preference toggle
3. **v0.8:** (Optional) Make form default, chat as "Advanced" option
4. **v0.9:** (Optional) Deprecate chat wizard if usage drops

---

## Accessibility Checklist

- ✅ Proper form labels (`<label>` for each input)
- ✅ ARIA attributes for progress (`aria-current="step"`)
- ✅ Keyboard navigation (Tab, Shift+Tab, Enter)
- ✅ Focus management (trap focus in modal)
- ✅ Color-coded, but also labeled (not color-only)
- ✅ Screen reader support (skip to main content)

---

## Why This Matters

**User Feedback Summary:**
> "The chat interface is clever, but I just want to fill out a form like any other web app. I'm familiar with that pattern."

**Market Research:**
- SaaS platforms standardize on multi-step form wizards
- Less cognitive load for non-technical users
- Better for enterprise deployments
- More accessible for diverse user bases

---

## Questions for Stakeholders

1. **Should we remove the chat wizard?**
   - No, keep both. Different users prefer different styles.

2. **Which should be the default?**
   - Recommendation: Let user choose on first raise, remember preference

3. **Should the form include AI suggestions?**
   - Yes! Each step can show LLM-suggested completions

4. **What about mobile?**
   - Form wizard works better on mobile (scrollable vs chat input)

---

## Effort & Timeline

| Task | Hours | Timeline |
|------|-------|----------|
| Core components | 5 | Week 1 |
| State management | 1 | Week 1 |
| API integration | 2 | Week 2 |
| Styling & UX | 2 | Week 2 |
| Testing | 1 | Week 2 |
| Optional: Hybrid toggle | 3 | Week 3 |
| **TOTAL** | **14** | **3 weeks** |

---

## Conclusion

A traditional form-based issue wizard would:
- ✅ Improve accessibility
- ✅ Serve enterprise users
- ✅ Reduce cognitive load
- ✅ Follow familiar UI patterns
- ✅ Work better on mobile

**Recommendation:** Build alongside chat wizard (hybrid approach), let users choose their preferred style.

---

**Status:** 🔴 Not in roadmap (proposal only)
**Estimated effort:** 8-14 hours
**Suggested priority:** v0.7.1 (after Bluesky integration)

