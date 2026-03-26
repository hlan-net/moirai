/**
 * Agent configuration constants shared across components.
 *
 * IMPORTANT: The ALLOWED_LOGIC_MODULES list must stay in sync with
 * api/validation.py::ALLOWED_LOGIC_MODULES (Python backend).
 * That list is the authoritative source of truth; this file mirrors it for UI use.
 */

export const ALLOWED_LOGIC_MODULES: string[] = [
  'tasks.agent_logic.create_event_from_articles',
  'tasks.agent_logic.add_articles_to_event',
  'tasks.agent_logic.check_event_staleness',
]

/**
 * Human-readable descriptions for each logic module.
 * Used in the Agent Management UI to help users understand what each module does.
 */
export const LOGIC_MODULE_INFO: Record<string, { name: string; description: string; useCase: string }> = {
  'tasks.agent_logic.create_event_from_articles': {
    name: 'Event Discovery',
    description: 'Analyzes incoming articles and creates new Events when significant patterns emerge.',
    useCase: 'Use when you want to automatically discover breaking news or emerging stories.',
  },
  'tasks.agent_logic.add_articles_to_event': {
    name: 'Event Enrichment',
    description: 'Matches new articles to existing Events based on relevance.',
    useCase: 'Use when you want to automatically grow existing Events with related coverage.',
  },
  'tasks.agent_logic.check_event_staleness': {
    name: 'Staleness Monitor',
    description: 'Reviews Events and marks them as stale if no new activity within threshold.',
    useCase: 'Use when you want to automatically archive Events that are no longer active.',
  },
}

/**
 * Trigger type descriptions for the UI.
 */
export const TRIGGER_TYPE_INFO: Record<string, { name: string; description: string }> = {
  'on_new_article': {
    name: 'On New Article',
    description: 'Runs whenever a new article is ingested into the system.',
  },
  'scheduled': {
    name: 'Scheduled',
    description: 'Runs at regular intervals (e.g., every hour, every day).',
  },
}
