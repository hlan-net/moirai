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
