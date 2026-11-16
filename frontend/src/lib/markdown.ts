// A small Markdown parser for the in-app documentation (Day 44). The docs are plain Markdown files in docs/guide/,
// so GitHub shows the same pages. Only the subset the docs use is supported:
//   headings (#–####), paragraphs, bullet and numbered lists (nested by indentation), fenced code blocks,
//   tables (GitHub style), blockquotes and GitHub callouts (> [!NOTE], [!TIP], [!IMPORTANT], [!WARNING],
//   [!CAUTION]), horizontal rules; inline `code`, **bold**, *italic*, [links](target) and <https://autolinks>.
// The parser builds plain objects; components/docs/Markdown.tsx turns them into React elements, so no HTML string
// is ever inserted into the page.

export type CalloutKind = 'note' | 'tip' | 'important' | 'warning' | 'caution'
export type Align = 'left' | 'center' | 'right' | null

export type Block =
  | { type: 'heading'; level: number; text: string; id: string }
  | { type: 'paragraph'; text: string }
  | { type: 'code'; lang: string; code: string }
  | { type: 'list'; ordered: boolean; start: number; items: Block[][] }
  | { type: 'table'; header: string[]; align: Align[]; rows: string[][] }
  | { type: 'callout'; kind: CalloutKind; blocks: Block[] }
  | { type: 'quote'; blocks: Block[] }
  | { type: 'rule' }

export type Inline =
  | { type: 'text'; value: string }
  | { type: 'code'; value: string }
  | { type: 'strong'; children: Inline[] }
  | { type: 'em'; children: Inline[] }
  | { type: 'link'; href: string; children: Inline[] }

export interface TocEntry {
  level: number
  text: string
  id: string
}

const HEADING = /^(#{1,6})\s+(.+?)\s*#*\s*$/
const FENCE = /^```\s*([\w+-]*)\s*$/
const RULE = /^(?:-{3,}|\*{3,}|_{3,})\s*$/
const LIST_ITEM = /^(\s*)([-*+]|\d+[.)])\s+(.*)$/
const TABLE_SEPARATOR = /^\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$/
const CALLOUT = /^\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]\s*$/i

/** Plain text of an inline string: markup removed (used for heading ids, the table of contents and search). */
export function plainText(text: string): string {
  return flatten(parseInline(text))
}

function flatten(nodes: Inline[]): string {
  return nodes.map((n) => (n.type === 'text' || n.type === 'code' ? n.value : flatten(n.children))).join('')
}

/** 'Start the stack (Docker)' -> 'start-the-stack-docker' (same idea as GitHub's heading anchors). */
export function slugify(text: string): string {
  return plainText(text)
    .toLowerCase()
    .replace(/[^\p{L}\p{N}\s-]/gu, '')
    .trim()
    .replace(/\s+/g, '-')
}

function isBlockStart(line: string): boolean {
  return HEADING.test(line) || FENCE.test(line.trim()) || RULE.test(line) || line.startsWith('>')
    || LIST_ITEM.test(line) || line.trimStart().startsWith('|')
}

function splitRow(line: string): string[] {
  let row = line.trim()
  if (row.startsWith('|')) row = row.slice(1)
  if (row.endsWith('|') && !row.endsWith('\\|')) row = row.slice(0, -1)
  const cells: string[] = []
  let cell = ''
  let inCode = false
  for (let i = 0; i < row.length; i++) {
    const ch = row[i]
    if (ch === '\\' && row[i + 1] === '|') {
      cell += '|'
      i++
    } else if (ch === '`') {
      inCode = !inCode
      cell += ch
    } else if (ch === '|' && !inCode) {
      cells.push(cell.trim())
      cell = ''
    } else {
      cell += ch
    }
  }
  cells.push(cell.trim())
  return cells
}

function alignOf(cell: string): Align {
  const left = cell.startsWith(':')
  const right = cell.endsWith(':')
  if (left && right) return 'center'
  if (right) return 'right'
  if (left) return 'left'
  return null
}

function indentOf(line: string): number {
  return line.length - line.trimStart().length
}

/** Parse a whole document. Heading ids are unique within the document. */
export function parseMarkdown(source: string): Block[] {
  const used = new Map<string, number>()
  return parseBlocks(source.replace(/\r\n?/g, '\n').split('\n'), used)
}

function uniqueId(text: string, used: Map<string, number>): string {
  const base = slugify(text) || 'section'
  const seen = used.get(base) ?? 0
  used.set(base, seen + 1)
  return seen ? `${base}-${seen}` : base
}

function parseBlocks(lines: string[], used: Map<string, number>): Block[] {
  const blocks: Block[] = []
  let i = 0
  while (i < lines.length) {
    const line = lines[i]
    if (!line.trim()) {
      i++
      continue
    }

    const fence = FENCE.exec(line.trim())
    if (fence && indentOf(line) < 4) {
      const indent = indentOf(line)
      const code: string[] = []
      i++
      while (i < lines.length && !/^```\s*$/.test(lines[i].trim())) {
        code.push(lines[i].slice(Math.min(indent, indentOf(lines[i]))))
        i++
      }
      i++                                            // closing fence
      blocks.push({ type: 'code', lang: fence[1].toLowerCase(), code: code.join('\n') })
      continue
    }

    const heading = HEADING.exec(line)
    if (heading) {
      const text = heading[2]
      blocks.push({ type: 'heading', level: heading[1].length, text, id: uniqueId(text, used) })
      i++
      continue
    }

    if (RULE.test(line)) {
      blocks.push({ type: 'rule' })
      i++
      continue
    }

    if (line.trimStart().startsWith('|') && i + 1 < lines.length && lines[i + 1].includes('|')
        && TABLE_SEPARATOR.test(lines[i + 1].trim())) {
      const header = splitRow(line)
      const align = splitRow(lines[i + 1]).map(alignOf)
      const rows: string[][] = []
      i += 2
      while (i < lines.length && lines[i].trimStart().startsWith('|')) {
        const cells = splitRow(lines[i])
        rows.push(header.map((_, c) => cells[c] ?? ''))
        i++
      }
      blocks.push({ type: 'table', header, align, rows })
      continue
    }

    if (line.startsWith('>')) {
      const inner: string[] = []
      while (i < lines.length && lines[i].startsWith('>')) {
        inner.push(lines[i].replace(/^>\s?/, ''))
        i++
      }
      const callout = inner.length ? CALLOUT.exec(inner[0].trim()) : null
      if (callout) {
        blocks.push({ type: 'callout', kind: callout[1].toLowerCase() as CalloutKind,
          blocks: parseBlocks(inner.slice(1), used) })
      } else {
        blocks.push({ type: 'quote', blocks: parseBlocks(inner, used) })
      }
      continue
    }

    const item = LIST_ITEM.exec(line)
    if (item && item[1].length === 0) {
      const ordered = /\d/.test(item[2])
      const start = ordered ? parseInt(item[2], 10) : 1
      const items: Block[][] = []
      while (i < lines.length) {
        const current = LIST_ITEM.exec(lines[i])
        if (!current || current[1].length !== 0 || /\d/.test(current[2]) !== ordered) break
        const contentIndent = lines[i].length - current[3].length
        const body: string[] = [current[3]]
        i++
        // the item continues with indented lines (nested lists, code, more text) and blank lines between them
        while (i < lines.length) {
          const next = lines[i]
          if (!next.trim()) {
            const following = lines.slice(i + 1).find((l) => l.trim())
            if (following !== undefined && indentOf(following) >= 2) {
              body.push('')
              i++
              continue
            }
            break
          }
          if (indentOf(next) >= 2) {
            body.push(next.slice(Math.min(contentIndent, indentOf(next))))
            i++
            continue
          }
          if (!isBlockStart(next)) {                 // lazy continuation of the item's first paragraph
            body.push(next.trim())
            i++
            continue
          }
          break
        }
        items.push(parseBlocks(body, used))
        while (i < lines.length && !lines[i].trim()) {
          const following = lines.slice(i + 1).find((l) => l.trim())
          if (following === undefined || !LIST_ITEM.test(following) || indentOf(following) !== 0) break
          i++                                        // blank lines between items of the same list
        }
      }
      blocks.push({ type: 'list', ordered, start, items })
      continue
    }

    const paragraph: string[] = [line.trim()]
    i++
    while (i < lines.length && lines[i].trim() && !isBlockStart(lines[i])) {
      paragraph.push(lines[i].trim())
      i++
    }
    blocks.push({ type: 'paragraph', text: paragraph.join(' ') })
  }
  return blocks
}

const INLINE = [
  { type: 'code', re: /`([^`]+)`/ },
  { type: 'autolink', re: /<(https?:\/\/[^\s>]+)>/ },
  { type: 'link', re: /\[((?:[^\]\\]|\\.)+)\]\(([^)\s]+)\)/ },
  { type: 'strong', re: /\*\*(?=\S)([\s\S]+?)\*\*/ },
  { type: 'em', re: /(?<![*\w])\*(?=[^\s*])([^*]+?)\*(?![*\w])/ },
] as const

/** Inline markup -> tree. The earliest match wins; code spans are never parsed further. */
export function parseInline(text: string): Inline[] {
  const out: Inline[] = []
  let rest = text
  while (rest) {
    let best: { type: string; match: RegExpExecArray } | null = null
    for (const { type, re } of INLINE) {
      const match = re.exec(rest)
      if (match && (!best || match.index < best.match.index)) best = { type, match }
    }
    if (!best) {
      out.push({ type: 'text', value: rest })
      break
    }
    const { type, match } = best
    if (match.index > 0) out.push({ type: 'text', value: rest.slice(0, match.index) })
    if (type === 'code') out.push({ type: 'code', value: match[1] })
    else if (type === 'autolink') out.push({ type: 'link', href: match[1], children: [{ type: 'text', value: match[1] }] })
    else if (type === 'link') out.push({ type: 'link', href: match[2], children: parseInline(match[1]) })
    else out.push({ type: type as 'strong' | 'em', children: parseInline(match[1]) })
    rest = rest.slice(match.index + match[0].length)
  }
  return merge(out)
}

function merge(nodes: Inline[]): Inline[] {
  const out: Inline[] = []
  for (const node of nodes) {
    const last = out[out.length - 1]
    if (node.type === 'text' && last?.type === 'text') last.value += node.value
    else out.push(node)
  }
  return out
}

/** Level-2 and level-3 headings, for the "On this page" list. */
export function tableOfContents(blocks: Block[]): TocEntry[] {
  return blocks
    .filter((b): b is Extract<Block, { type: 'heading' }> => b.type === 'heading' && (b.level === 2 || b.level === 3))
    .map((b) => ({ level: b.level, text: plainText(b.text), id: b.id }))
}

/** The document's first level-1 heading, if any. */
export function documentTitle(blocks: Block[]): string | null {
  const h1 = blocks.find((b) => b.type === 'heading' && b.level === 1)
  return h1 && h1.type === 'heading' ? plainText(h1.text) : null
}