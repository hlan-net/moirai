<script setup lang="ts">
import { onMounted, ref } from 'vue'

interface MythologyStats {
  feeds: number
  articles: number
  issues: number
}

interface PublicIssue {
  _id: string
  logos: string
  description: string
  longevity: 'transient' | 'temporal' | 'epic'
  status: 'active' | 'eternal'
  born_at?: string
  premises_count: number
}

interface MythologyData {
  stats: MythologyStats
  public_issues: PublicIssue[]
}

const data = ref<MythologyData | null>(null)
const loading = ref(true)
const error = ref(false)

const longevityLabel: Record<string, string> = {
  transient: 'Event',
  temporal: 'Trend',
  epic: 'Epic',
}

const formatDate = (iso?: string): string => {
  if (!iso) return ''
  try {
    return new Date(iso).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
  } catch {
    return ''
  }
}

onMounted(async () => {
  try {
    const res = await fetch('/api/mythology')
    if (res.ok) {
      data.value = await res.json()
    } else {
      error.value = true
    }
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="mythology-page">
    <header class="myth-header">
      <h1>The Three Fates</h1>
      <p class="myth-subtitle">
        Moirai — the Greek goddesses of fate — spin, measure, and cut the thread of life. This
        platform takes their names and their nature.
      </p>
    </header>

    <section class="fate-section">
      <div class="fate-card clotho">
        <div class="fate-icon">🪡</div>
        <h2>Clotho</h2>
        <p class="fate-role">The Spinner</p>
        <p class="fate-description">
          Clotho spins the thread of life from her distaff onto her spindle. In Moirai, she is the
          layer of <strong>ingestion</strong> — the RSS feeds that draw raw information from the
          world and wind it into the system. Every feed is a new thread beginning; every article a
          length of that thread laid down.
        </p>
        <div v-if="data" class="fate-stat">
          <span class="stat-number">{{ data.stats.feeds }}</span>
          <span class="stat-label">feeds spinning</span>
        </div>
      </div>

      <div class="fate-card lachesis">
        <div class="fate-icon">📏</div>
        <h2>Lachesis</h2>
        <p class="fate-role">The Allotter</p>
        <p class="fate-description">
          Lachesis measures the thread and assigns each soul its destiny. In Moirai, she is the
          layer of <strong>meaning-making</strong> — issues that group, name, and track the
          patterns emerging from the flow of articles. An issue is an act of measurement: this
          matters, this will last, this is what is happening. Each issue defines its own evaluation
          cadence, knowing when it should be revisited and how long its thread should run.
        </p>
        <div v-if="data" class="fate-stat">
          <span class="stat-number">{{ data.stats.articles }}</span>
          <span class="stat-label">articles measured</span>
        </div>
      </div>

      <div class="fate-card atropos">
        <div class="fate-icon">✂️</div>
        <h2>Atropos</h2>
        <p class="fate-role">The Inflexible</p>
        <p class="fate-description">
          Atropos — the inevitable — cuts the thread at the appointed time. In Moirai, she is the
          layer of <strong>agent execution</strong>: the agents that act upon issues, decide what
          is still alive, what has grown stale, and what should be sealed into eternity. She does
          not deliberate; she acts on the cadence set by the issue she serves.
        </p>
        <div v-if="data" class="fate-stat">
          <span class="stat-number">{{ data.stats.issues }}</span>
          <span class="stat-label">issues in the weave</span>
        </div>
      </div>
    </section>

    <section class="distaff-section">
      <h2>The Distaff — Userspace</h2>
      <p>
        The distaff is the tool that holds the raw fibre before it is spun. In Moirai, the
        <strong>userspace</strong> is the distaff: it holds the LLM credentials, the data
        isolation, the capability from which every thread is drawn. Nothing is spun without a
        distaff. Every feed, every issue, every agent belongs to a userspace — and the quality of
        the thread depends on what the distaff holds.
      </p>
      <p>
        Plato, in the <em>Republic</em>, used the Fates to close his vision of a just order. The
        spindle of Necessity turns at the centre of the cosmos; the three sisters sing in harmony
        with the spheres. In Moirai, the userspace is that centre — the still point around which
        the rest revolves.
      </p>
    </section>

    <section class="public-issues-section">
      <h2>The Living Weave</h2>
      <p class="section-intro">
        Below are issues that the system has made public — threads visible to any eye, a window
        into what is being tracked and measured right now.
      </p>

      <div v-if="loading" class="loading-state">Consulting the Fates…</div>
      <div v-else-if="error" class="error-state">The oracle is silent. Try again later.</div>
      <div v-else-if="!data?.public_issues.length" class="empty-state">
        No issues have been made public yet. Administrators can mark issues as public from the
        Dashboard.
      </div>
      <div v-else class="issues-grid">
        <div
          v-for="issue in data.public_issues"
          :key="issue._id"
          class="issue-card"
          :class="issue.longevity"
        >
          <div class="issue-meta">
            <span class="longevity-badge">{{ longevityLabel[issue.longevity] ?? issue.longevity }}</span>
            <span class="status-badge" :class="issue.status">{{ issue.status }}</span>
          </div>
          <h3>{{ issue.logos }}</h3>
          <p class="issue-description">{{ issue.description }}</p>
          <div class="issue-footer">
            <span v-if="issue.born_at" class="issue-date">Born {{ formatDate(issue.born_at) }}</span>
            <span class="premises-count">{{ issue.premises_count }} premises</span>
          </div>
        </div>
      </div>
    </section>

    <footer class="myth-footer">
      <p>
        <em>
          "The spindle of Necessity turns, and the three Fates sing — Lachesis of the past,
          Clotho of the present, Atropos of the future." — Plato, Republic X
        </em>
      </p>
    </footer>
  </div>
</template>

<style scoped>
.mythology-page {
  max-width: 1100px;
  margin: 0 auto;
  padding: 40px 20px;
  color: var(--text-color);
  overflow-y: auto;
  height: 100%;
}

.myth-header {
  text-align: center;
  margin-bottom: 48px;
}

.myth-header h1 {
  font-size: 2.4rem;
  margin: 0 0 12px 0;
  color: #d83b01;
  letter-spacing: 0.04em;
}

.myth-subtitle {
  font-size: 1.1rem;
  opacity: 0.8;
  max-width: 600px;
  margin: 0 auto;
  line-height: 1.6;
}

/* Three Fates */
.fate-section {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 24px;
  margin-bottom: 48px;
}

.fate-card {
  background: var(--card-bg);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 28px 24px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.fate-card.clotho {
  border-top: 3px solid #2e86c1;
}
.fate-card.lachesis {
  border-top: 3px solid #d4ac0d;
}
.fate-card.atropos {
  border-top: 3px solid #d83b01;
}

.fate-icon {
  font-size: 2rem;
}

.fate-card h2 {
  margin: 0;
  font-size: 1.5rem;
  color: var(--text-color);
}

.fate-role {
  font-size: 0.85rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  opacity: 0.6;
  margin: 0;
}

.fate-description {
  font-size: 0.95rem;
  line-height: 1.65;
  opacity: 0.85;
  margin: 0;
  flex: 1;
}

.fate-stat {
  margin-top: 8px;
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.stat-number {
  font-size: 2rem;
  font-weight: bold;
  color: #d83b01;
}

.stat-label {
  font-size: 0.85rem;
  opacity: 0.7;
}

/* Distaff */
.distaff-section {
  background: var(--card-bg);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 32px;
  margin-bottom: 48px;
}

.distaff-section h2 {
  margin: 0 0 16px 0;
  color: var(--text-color);
}

.distaff-section p {
  line-height: 1.7;
  opacity: 0.85;
  margin: 0 0 12px 0;
}

/* Public issues */
.public-issues-section {
  margin-bottom: 48px;
}

.public-issues-section h2 {
  margin: 0 0 8px 0;
  color: var(--text-color);
}

.section-intro {
  opacity: 0.75;
  margin: 0 0 24px 0;
  line-height: 1.6;
}

.loading-state,
.error-state,
.empty-state {
  text-align: center;
  padding: 40px;
  opacity: 0.6;
  font-style: italic;
}

.issues-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 20px;
}

.issue-card {
  background: var(--card-bg);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.issue-card.transient {
  border-left: 3px solid #d83b01;
}
.issue-card.temporal {
  border-left: 3px solid #d4ac0d;
}
.issue-card.epic {
  border-left: 3px solid #2e86c1;
}

.issue-meta {
  display: flex;
  gap: 8px;
  align-items: center;
}

.longevity-badge {
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  background: rgba(255, 255, 255, 0.08);
  padding: 2px 8px;
  border-radius: 4px;
}

.status-badge {
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  padding: 2px 8px;
  border-radius: 4px;
}
.status-badge.active {
  background: #166534;
  color: white;
}
.status-badge.eternal {
  background: #6c757d;
  color: white;
}

.issue-card h3 {
  margin: 0;
  font-size: 1.05rem;
  color: var(--text-color);
  line-height: 1.4;
}

.issue-description {
  font-size: 0.88rem;
  line-height: 1.55;
  opacity: 0.8;
  margin: 0;
  flex: 1;
}

.issue-footer {
  display: flex;
  justify-content: space-between;
  font-size: 0.78rem;
  opacity: 0.55;
  margin-top: 4px;
}

/* Footer */
.myth-footer {
  text-align: center;
  padding: 24px 0 8px 0;
  border-top: 1px solid var(--border-color);
  opacity: 0.5;
  font-size: 0.9rem;
}
</style>
