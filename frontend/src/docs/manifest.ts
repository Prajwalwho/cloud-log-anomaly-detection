// The in-app documentation: which pages exist, in which order, and where links point.
// The pages are the Markdown files in docs/guide/ at the repository root (one source for GitHub and the app).
// To add a page: write docs/guide/<slug>.md (starting with a "# Title" line) and add its slug to SECTIONS below.
import type { LinkTarget } from '../components/docs/Markdown'
import { type Block, documentTitle, parseMarkdown, plainText } from '../lib/markdown'

export const REPO_URL = 'https://github.com/Prajwalwho/cloud-log-anomaly-detection'
const GUIDE_DIR = '../../../docs/guide/'

const FILES = import.meta.glob('../../../docs/guide/*.md', {
  query: '?raw', import: 'default', eager: true,
}) as Record<string, string>

export const SECTIONS: { title: string; slugs: string[] }[] = [
  { title: 'Start here', slugs: ['introduction', 'getting-started'] },
  { title: 'Learn', slugs: ['concepts', 'how-detection-works'] },
  { title: 'Use', slugs: ['using-the-dashboard', 'alerts-and-telegram', 'operations'] },
]

export interface DocPage {
  slug: string
  title: string
  section: string
  blocks: Block[]
  lines: string[]          // plain text per source line, for search
}

export const PAGES: DocPage[] = SECTIONS.flatMap(({ title: section, slugs }) =>
  slugs.flatMap((slug) => {
    const source = FILES[`${GUIDE_DIR}${slug}.md`]
    if (source === undefined) return []        // listed but not written yet
    const blocks = parseMarkdown(source)
    return [{
      slug,
      section,
      blocks,
      title: documentTitle(blocks) ?? slug,
      lines: source.split('\n')
        .filter((line) => !line.trim().startsWith('```') && !/^\|?[\s:|-]+\|?$/.test(line.trim()))
        .map((line) => plainText(line.replace(/^[#>\s-]+|\|/g, ' ')).trim())
        .filter(Boolean),
    }]
  }),
)

export const FIRST_SLUG = PAGES[0]?.slug ?? 'introduction'

export function getPage(slug: string): DocPage | undefined {
  return PAGES.find((p) => p.slug === slug)
}

export function neighbours(slug: string): { previous?: DocPage; next?: DocPage } {
  const i = PAGES.findIndex((p) => p.slug === slug)
  return i < 0 ? {} : { previous: PAGES[i - 1], next: PAGES[i + 1] }
}

export function sourceUrl(slug: string): string {
  return `${REPO_URL}/blob/main/docs/guide/${slug}.md`
}

/** Where a link written in a docs page goes: another docs page, a heading on this page, or a new tab. */
export function resolveDocLink(href: string): LinkTarget {
  if (/^(https?:|mailto:)/.test(href)) return { kind: 'external', to: href }
  if (href.startsWith('#')) return { kind: 'anchor', to: href }
  const page = /^(?:\.\/)?([\w-]+)\.md(#[\w-]+)?$/.exec(href)
  if (page && getPage(page[1])) return { kind: 'route', to: `/docs/${page[1]}${page[2] ?? ''}` }
  // any other file of the repository (design documents, scripts, ...): show it on GitHub
  return { kind: 'external', to: new URL(href, `${REPO_URL}/blob/main/docs/guide/`).toString() }
}

export interface SearchHit {
  page: DocPage
  snippet: string
}

/** Pages whose title or text contains every word of the query; title matches first. */
export function searchDocs(query: string, limit = 8): SearchHit[] {
  const words = query.toLowerCase().split(/\s+/).filter(Boolean)
  if (!words.length) return []
  const hits: (SearchHit & { score: number })[] = []
  for (const page of PAGES) {
    const title = page.title.toLowerCase()
    const body = page.lines.join(' ').toLowerCase()
    if (!words.every((w) => title.includes(w) || body.includes(w))) continue
    const line = page.lines.find((l) => l.toLowerCase().includes(words[0])) ?? page.lines[1] ?? ''
    const at = Math.max(0, line.toLowerCase().indexOf(words[0]) - 40)
    const snippet = (at > 0 ? '…' : '') + line.slice(at, at + 140) + (line.length > at + 140 ? '…' : '')
    hits.push({ page, snippet, score: words.every((w) => title.includes(w)) ? 0 : 1 })
  }
  return hits.sort((a, b) => a.score - b.score).slice(0, limit)
}