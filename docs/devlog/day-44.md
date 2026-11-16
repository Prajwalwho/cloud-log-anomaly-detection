# Day 44 — Documentation inside the app (Phase 11 starts)

## Plan for Phase 11
- Day 44: Docs section in the dashboard; Introduction, Getting started.
- Day 45: concepts, how detection works.
- Day 46: using the dashboard, alerts and Telegram, operations.
- Day 47: architecture, API and configuration reference, glossary and FAQ; README rewritten.
- Day 48: study guide; final link and build check.

## Built
- One source for the guide: Markdown files in `docs/guide/`. GitHub shows them as pages; the dashboard shows the
  same files under **Docs** (`/docs/<page>`), so the two cannot drift apart.
- `frontend/src/lib/markdown.ts`: a small parser for the subset the guide uses (headings with GitHub-style ids,
  paragraphs, nested lists, code blocks, tables with alignment, GitHub callouts, inline code, bold, italic, links).
  It builds plain objects; `components/docs/Markdown.tsx` turns them into React elements, so no HTML string is ever
  put into the page. No new dependency.
- `frontend/src/docs/manifest.ts`: sections and page order, links (`other-page.md` stays in the app, other repository
  files open on GitHub, websites in a new tab), search over titles and text.
- `pages/Docs.tsx`: sidebar with search, the page, "On this page" with links to every section, previous/next,
  "View this page on GitHub"; copy buttons on code blocks; works on a phone width.
- Layout: **Docs** in the navigation; the time range picker is hidden on documentation pages.
- `vite.config.ts`: the dev server may read `../docs` (outside the frontend folder).
- Pages: `introduction.md` (problem, what it does, how it works, what it detects, measured results, limits, parts),
  `getting-started.md` (setup, start, model training, Telegram, services, first fault, stopping, laptop power,
  common problems), `docs/guide/README.md` (index and how to write a page).

## Checked
- Parser on a test document (nested lists with code, tables with escaped pipes and alignment, callouts, duplicate
  headings get `-1` like GitHub).
- Rendered with the real components: desktop and phone width, search, page switch, anchors.

## Next
- Day 45: concepts and how detection works.