// Renders parsed Markdown (lib/markdown.ts) as React elements, in the Observatory style. Links between docs pages
// stay inside the app; links to other repository files and websites open in a new tab.
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Check, Copy, Info, Lightbulb, MessageSquareWarning, OctagonAlert, TriangleAlert } from 'lucide-react'
import type { Block, CalloutKind, Inline } from '../../lib/markdown'
import { parseInline } from '../../lib/markdown'

export type LinkTarget =
  | { kind: 'route'; to: string }
  | { kind: 'anchor'; to: string }
  | { kind: 'external'; to: string }

type Resolve = (href: string) => LinkTarget

const CALLOUTS: Record<CalloutKind, { label: string; icon: typeof Info }> = {
  note: { label: 'Note', icon: Info },
  tip: { label: 'Tip', icon: Lightbulb },
  important: { label: 'Important', icon: MessageSquareWarning },
  warning: { label: 'Warning', icon: TriangleAlert },
  caution: { label: 'Caution', icon: OctagonAlert },
}

function Inlines({ nodes, resolve }: { nodes: Inline[]; resolve: Resolve }) {
  return (
    <>
      {nodes.map((node, i) => {
        switch (node.type) {
          case 'text':
            return node.value
          case 'code':
            return <code key={i}>{node.value}</code>
          case 'strong':
            return <strong key={i}><Inlines nodes={node.children} resolve={resolve} /></strong>
          case 'em':
            return <em key={i}><Inlines nodes={node.children} resolve={resolve} /></em>
          case 'link': {
            const target = resolve(node.href)
            const children = <Inlines nodes={node.children} resolve={resolve} />
            if (target.kind === 'route') return <Link key={i} to={target.to}>{children}</Link>
            if (target.kind === 'anchor') return <a key={i} href={target.to}>{children}</a>
            return <a key={i} href={target.to} target="_blank" rel="noreferrer">{children}</a>
          }
        }
      })}
    </>
  )
}

function Text({ text, resolve }: { text: string; resolve: Resolve }) {
  return <Inlines nodes={parseInline(text)} resolve={resolve} />
}

function CodeBlock({ lang, code }: { lang: string; code: string }) {
  const [copied, setCopied] = useState(false)
  const copy = () => {
    navigator.clipboard?.writeText(code).then(() => {
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1500)
    }).catch(() => undefined)
  }
  return (
    <div className={lang === 'text' ? 'md-code' : 'md-code md-code-wrap'}>
      <div className="md-code-bar">
        <span>{lang || 'text'}</span>
        <button type="button" onClick={copy} aria-label="Copy code">
          {copied ? <Check size={14} aria-hidden="true" /> : <Copy size={14} aria-hidden="true" />}
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>
      <pre><code>{code}</code></pre>
    </div>
  )
}

function ListItemBody({ blocks, resolve }: { blocks: Block[]; resolve: Resolve }) {
  const [first, ...rest] = blocks
  if (first?.type === 'paragraph') {
    return (
      <>
        <Text text={first.text} resolve={resolve} />
        <Blocks blocks={rest} resolve={resolve} />
      </>
    )
  }
  return <Blocks blocks={blocks} resolve={resolve} />
}

function BlockView({ block, resolve }: { block: Block; resolve: Resolve }) {
  switch (block.type) {
    case 'heading': {
      const content = <Text text={block.text} resolve={resolve} />
      const anchor = block.level >= 2 && block.level <= 3
        ? <a className="md-anchor" href={`#${block.id}`} aria-label="Link to this section">#</a>
        : null
      if (block.level === 1) return <h1 id={block.id}>{content}</h1>
      if (block.level === 2) return <h2 id={block.id}>{content}{anchor}</h2>
      if (block.level === 3) return <h3 id={block.id}>{content}{anchor}</h3>
      return <h4 id={block.id}>{content}</h4>
    }
    case 'paragraph':
      return <p><Text text={block.text} resolve={resolve} /></p>
    case 'code':
      return <CodeBlock lang={block.lang} code={block.code} />
    case 'list': {
      const items = block.items.map((item, i) => <li key={i}><ListItemBody blocks={item} resolve={resolve} /></li>)
      return block.ordered ? <ol start={block.start}>{items}</ol> : <ul>{items}</ul>
    }
    case 'table':
      return (
        <div className="md-table-wrap">
          <table className="md-table">
            <thead>
              <tr>
                {block.header.map((cell, c) => (
                  <th key={c} style={{ textAlign: block.align[c] ?? undefined }}><Text text={cell} resolve={resolve} /></th>
                ))}
              </tr>
            </thead>
            <tbody>
              {block.rows.map((row, r) => (
                <tr key={r}>
                  {row.map((cell, c) => (
                    <td key={c} style={{ textAlign: block.align[c] ?? undefined }}><Text text={cell} resolve={resolve} /></td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )
    case 'callout': {
      const { label, icon: Icon } = CALLOUTS[block.kind]
      return (
        <div className={`md-callout md-callout-${block.kind}`}>
          <div className="md-callout-title"><Icon size={16} aria-hidden="true" />{label}</div>
          <Blocks blocks={block.blocks} resolve={resolve} />
        </div>
      )
    }
    case 'quote':
      return <blockquote><Blocks blocks={block.blocks} resolve={resolve} /></blockquote>
    case 'rule':
      return <hr />
  }
}

function Blocks({ blocks, resolve }: { blocks: Block[]; resolve: Resolve }) {
  return <>{blocks.map((block, i) => <BlockView key={i} block={block} resolve={resolve} />)}</>
}

export function Markdown({ blocks, resolve }: { blocks: Block[]; resolve: Resolve }) {
  return <div className="md"><Blocks blocks={blocks} resolve={resolve} /></div>
}