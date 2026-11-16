// Documentation (Phase 11): the guide in docs/guide/, read inside the app. Left: sections and search; middle: the
// page; right: "On this page". The address is /docs/<page>#<heading>, so every section can be linked.
import { useEffect, useMemo, useState } from 'react'
import { Link, NavLink, useLocation, useParams } from 'react-router-dom'
import { ArrowLeft, ArrowRight, BookOpen, ExternalLink, Search, X } from 'lucide-react'
import { Markdown } from '../components/docs/Markdown'
import { FIRST_SLUG, getPage, neighbours, resolveDocLink, searchDocs, SECTIONS, sourceUrl } from '../docs/manifest'
import { tableOfContents } from '../lib/markdown'
import '../components/docs/docs.css'

function DocsNav({ current }: { current: string }) {
  const [query, setQuery] = useState('')
  const hits = useMemo(() => (query.trim().length >= 2 ? searchDocs(query) : []), [query])
  const searching = query.trim().length >= 2

  return (
    <aside className="docs-nav" aria-label="Documentation">
      <div className="docs-search">
        <Search size={15} aria-hidden="true" />
        <input type="search" value={query} placeholder="Search the docs" aria-label="Search the docs"
          onChange={(e) => setQuery(e.target.value)} />
        {query && (
          <button type="button" onClick={() => setQuery('')} aria-label="Clear search"><X size={14} /></button>
        )}
      </div>
      {searching ? (
        <div className="docs-hits">
          {hits.length === 0 && <p className="muted">Nothing found for “{query.trim()}”.</p>}
          {hits.map(({ page, snippet }) => (
            <Link key={page.slug} to={`/docs/${page.slug}`} className="docs-hit" onClick={() => setQuery('')}>
              <span className="docs-hit-title">{page.title}</span>
              <span className="docs-hit-snippet">{snippet}</span>
            </Link>
          ))}
        </div>
      ) : (
        SECTIONS.map((section) => {
          const pages = section.slugs.map(getPage).filter((p) => p !== undefined)
          if (!pages.length) return null
          return (
            <div key={section.title} className="docs-section">
              <div className="docs-section-title">{section.title}</div>
              {pages.map((p) => (
                <NavLink key={p.slug} to={`/docs/${p.slug}`} className={p.slug === current ? 'active' : ''}>
                  {p.title}
                </NavLink>
              ))}
            </div>
          )
        })
      )}
    </aside>
  )
}

export function Docs() {
  const { slug = FIRST_SLUG } = useParams()
  const { hash } = useLocation()
  const page = getPage(slug)
  const toc = useMemo(() => (page ? tableOfContents(page.blocks) : []), [page])
  const { previous, next } = neighbours(slug)

  // a new page starts at its top; a #heading in the address scrolls to that heading
  useEffect(() => {
    const target = hash ? document.getElementById(decodeURIComponent(hash.slice(1))) : null
    if (target) target.scrollIntoView({ block: 'start' })
    else window.scrollTo({ top: 0 })
  }, [slug, hash])

  return (
    <div className="docs">
      <DocsNav current={slug} />

      <article className="docs-article">
        {page ? (
          <>
            <div className="docs-crumb"><BookOpen size={14} aria-hidden="true" />Docs · {page.section}</div>
            <Markdown blocks={page.blocks} resolve={resolveDocLink} />
            <footer className="docs-footer">
              <div className="docs-pager">
                {previous ? (
                  <Link to={`/docs/${previous.slug}`} className="docs-pager-link">
                    <span className="docs-pager-label"><ArrowLeft size={14} aria-hidden="true" />Previous</span>
                    {previous.title}
                  </Link>
                ) : <span />}
                {next && (
                  <Link to={`/docs/${next.slug}`} className="docs-pager-link next">
                    <span className="docs-pager-label">Next<ArrowRight size={14} aria-hidden="true" /></span>
                    {next.title}
                  </Link>
                )}
              </div>
              <a className="docs-source" href={sourceUrl(page.slug)} target="_blank" rel="noreferrer">
                <ExternalLink size={13} aria-hidden="true" />View this page on GitHub
              </a>
            </footer>
          </>
        ) : (
          <div className="docs-missing">
            <h1>Page not found</h1>
            <p className="lead">There is no documentation page called “{slug}”.</p>
            <p><Link to={`/docs/${FIRST_SLUG}`}>Go to the introduction</Link></p>
          </div>
        )}
      </article>

      {toc.length > 0 && (
        <nav className="docs-toc" aria-label="On this page">
          <div className="docs-section-title">On this page</div>
          {toc.map((entry) => (
            <a key={entry.id} href={`#${entry.id}`} className={entry.level === 3 ? 'sub' : ''}>{entry.text}</a>
          ))}
        </nav>
      )}
    </div>
  )
}