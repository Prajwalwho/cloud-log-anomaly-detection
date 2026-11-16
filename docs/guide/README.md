# Observatory guide

The user guide of *Cloud Log Anomaly Detection for Proactive Fault Management*. The same pages are shown inside the dashboard under **Docs** (<http://localhost:5173/docs>).

| Section | Page | What it covers |
|---|---|---|
| Start here | [Introduction](introduction.md) | What the system does, how it works, how well it works |
| Start here | [Getting started](getting-started.md) | Install, train the model, start everything, catch the first fault |
| Learn | [Concepts](concepts.md) | The words used everywhere: window, template, anomaly, severity, alert, offset, … |
| Learn | [How detection works](how-detection-works.md) | From a log line to an anomaly: Drain, windows, features, PCA, threshold, severity, timing |
| Learn | [Architecture](architecture.md) | The parts, the data flow, where data lives, one fault end to end, design decisions, failures, limits |
| Use | [Using the dashboard](using-the-dashboard.md) | Every page of the dashboard and what each part means |
| Use | [Alerts and Telegram](alerts-and-telegram.md) | How anomalies become alerts, their life, Telegram messages and setup, settings |
| Use | [Operations](operations.md) | Starting and stopping, health and consumer lag, disk space, retraining, tests, measuring, troubleshooting |
| Reference | [API reference](api-reference.md) | Every endpoint, its parameters and answers, and the live feed |
| Reference | [Configuration](configuration.md) | Every setting in `.env`, every command-line option, the scripts |
| Reference | [Glossary](glossary.md) | Every term in one line |
| Reference | [FAQ](faq.md) | Common questions about detection, using the system, and small problems |

## Writing a page

- One Markdown file per page, starting with a `# Title` line. The file name is the page's address: `getting-started.md` is `/docs/getting-started`.
- Add the page to `SECTIONS` in `frontend/src/docs/manifest.ts` so it appears in the app's sidebar, and to the table above.
- Link to other pages by file name (`[Getting started](getting-started.md)`), so links work on GitHub and in the app. Links to other files of the repository (for example `../testing/load-test-results.md`) open on GitHub.
- Supported Markdown: headings, paragraphs, lists, code blocks, tables, quotes, GitHub callouts (`> [!NOTE]`, `[!TIP]`, `[!IMPORTANT]`, `[!WARNING]`, `[!CAUTION]`), `code`, **bold**, *italic* and links. The parser is `frontend/src/lib/markdown.ts`.