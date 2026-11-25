// What the Stream page's side column is open on (#376): an article of the
// stream, or an issue (an event or a trend). The subject lives in the page's
// `open` query parameter, so Back closes the column and a view can be shared.

export type SubjectRef = { type: 'article'; link: string } | { type: 'issue'; id: string }

const ARTICLE_PREFIX = 'article:'
const ISSUE_PREFIX = 'issue:'

/** Reads the `open` query value; null for anything that is not a subject. */
export const parseSubject = (value: unknown): SubjectRef | null => {
  if (typeof value !== 'string') return null
  if (value.startsWith(ARTICLE_PREFIX)) {
    const link = value.slice(ARTICLE_PREFIX.length)
    return link ? { type: 'article', link } : null
  }
  if (value.startsWith(ISSUE_PREFIX)) {
    const id = value.slice(ISSUE_PREFIX.length)
    // Issue ids go into a request path; keep to the characters the API accepts.
    return /^[A-Za-z0-9_-]+$/.test(id) ? { type: 'issue', id } : null
  }
  return null
}

export const formatSubject = (subject: SubjectRef): string =>
  subject.type === 'article' ? `${ARTICLE_PREFIX}${subject.link}` : `${ISSUE_PREFIX}${subject.id}`

export const sameSubject = (a: SubjectRef | null, b: SubjectRef | null): boolean =>
  (a === null && b === null) || (a !== null && b !== null && formatSubject(a) === formatSubject(b))
