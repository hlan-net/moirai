// Stream sections (#266, #344): a fixed editorial split of the article flow.
// The sections are a partition (tasks/sections.py), so a choice of several is
// their union, and none or all of them is the whole stream.

export type SectionKey = 'main' | 'sports' | 'culture' | 'business'

export interface Section {
  key: SectionKey
  label: string
}

export const SECTIONS: Section[] = [
  { key: 'main', label: 'Top stories' },
  { key: 'sports', label: 'Sports' },
  { key: 'culture', label: 'Culture' },
  { key: 'business', label: 'Business' },
]

// First visit: Top stories only (decision 1 on #344).
export const DEFAULT_SECTIONS: SectionKey[] = ['main']

// The value of the page's `sections` query parameter and of the stored choice
// for the whole stream.
export const ALL_SECTIONS_VALUE = 'all'

export const SECTIONS_STORAGE_KEY = 'moirai.stream.sections'

const isSectionKey = (value: string): value is SectionKey =>
  SECTIONS.some((section) => section.key === value)

/** The chosen sections in SECTIONS order, without duplicates. */
export const canonicalSections = (keys: Iterable<string>): SectionKey[] => {
  const chosen = new Set(keys)
  return SECTIONS.map((section) => section.key).filter((key) => chosen.has(key))
}

/** True when the choice is the whole stream: none ticked (decision 2 on #344) or all. */
export const isWholeStream = (keys: SectionKey[]): boolean =>
  keys.length === 0 || keys.length === SECTIONS.length

/**
 * Reads a stored or linked choice: `all`, or a comma-separated list of
 * sections. Returns null for anything else, so the caller falls back.
 */
export const parseSectionsValue = (value: unknown): SectionKey[] | null => {
  if (typeof value !== 'string' || value.trim() === '') return null
  if (value === ALL_SECTIONS_VALUE) return SECTIONS.map((section) => section.key)
  const parts = value.split(',').map((part) => part.trim())
  if (!parts.every(isSectionKey)) return null
  return canonicalSections(parts)
}

/** The choice as a query or storage value: `all`, or `sports,culture` in SECTIONS order. */
export const formatSectionsValue = (keys: SectionKey[]): string =>
  isWholeStream(keys) ? ALL_SECTIONS_VALUE : canonicalSections(keys).join(',')

/** The `section` parameter of /api/stream.rss, or null for the whole stream. */
export const sectionsParam = (keys: SectionKey[]): string | null =>
  isWholeStream(keys) ? null : canonicalSections(keys).join(',')

/** What the page names next to the article count. */
export const sectionsSummary = (keys: SectionKey[]): string =>
  isWholeStream(keys)
    ? 'All sections'
    : SECTIONS.filter((section) => keys.includes(section.key))
        .map((section) => section.label)
        .join(', ')

export const readStoredSections = (): SectionKey[] | null => {
  try {
    return parseSectionsValue(localStorage.getItem(SECTIONS_STORAGE_KEY))
  } catch {
    return null
  }
}

export const storeSections = (keys: SectionKey[]): void => {
  try {
    localStorage.setItem(SECTIONS_STORAGE_KEY, formatSectionsValue(keys))
  } catch {
    // Storage may be unavailable (private mode); the URL still carries the choice.
  }
}
