# Using the dashboard

The dashboard, called *Observatory*, runs at <http://localhost:5173> once the services and `npm run dev` are started (see [Getting started](getting-started.md)). This page explains every page and what each part of it means.

## Everywhere

| Part | Where | What it does |
|---|---|---|
| Navigation | left sidebar | Overview, Anomalies, Alerts, Logs, Models, Docs |
| *All systems running* | bottom of the sidebar | The API checks PostgreSQL, Elasticsearch and Kafka every 30 seconds. If one is down, its name is shown in red; *Backend unreachable* means the API itself is not running |
| *Live updates on* | bottom of the sidebar | The live feed is connected. *Connecting* or *Reconnecting* means it is trying again by itself |
| Time range | top bar | 15 min, 1 hour, 6 hours, 24 hours or 7 days. It applies to every page at once |

Times are shown in your browser's local time; the API and the database work in UTC.

The filters and the selected item of each page are part of the address. Any view can be bookmarked, reloaded or sent to someone, and the browser's back button works as expected.

> [!TIP]
> New anomalies and alerts arrive through the live feed without reloading. The Logs page is the exception: it loads new lines only when you press **Refresh**, so the list does not move while you read it.

## Overview

The first page answers *"Is everything all right, and if not, where?"*

### The galaxy

The five services as a small galaxy. The **API gateway**, which receives every request, is the centre; the other services orbit it. The moving dots are requests flowing from the gateway to the services, more of them to the services that log more.

| What you see | What it means |
|---|---|
| Size of a planet | How many log lines the service wrote in the time range |
| Pale colour | Healthy |
| Yellow | Error rate of 5% or more, or an open MEDIUM alert |
| Orange / red | An open HIGH / CRITICAL alert |
| A ring (halo) | The service has an open alert |
| A flare | A new anomaly for this service has just arrived |

Point at a service to pause the motion; click it to open its anomalies. If your operating system is set to reduce motion, the galaxy stands still.

### The readout

Four numbers next to the galaxy, for the chosen time range:

- **Open alerts**: alerts not yet resolved (open or acknowledged). Click to open the Alerts page.
- **Anomalies**: how many minutes were flagged, with a bar showing how many of each severity.
- **Error rate**: the share of all log lines that were errors.
- **Log lines analysed**: how many lines the detection service judged, in how many service-minutes (windows).

### Charts

- **Activity across services**: one row per service, one cell per time step, coloured by how unusual the logs were (the highest score in that step). Hover a cell for its value. A fault shows up as a warm streak in one or more rows.
- **Error rate**: the share of error lines per service over time.
- **When anomalies happened**: flagged minutes per time step, stacked by service.

The time step is one minute for 15 minutes and one hour, five minutes for six hours, and one hour for 24 hours and seven days.

### Live signals

New anomalies, opened alerts and changed alerts, the moment they happen. It starts empty when the page is opened.

## Anomalies

Every flagged minute in the time range, newest first.

**Filters:** service, severity (several can be chosen), and review state (*All*, *Not reviewed*, *Confirmed*, *False positive*).

**The list** shows the minute, the service, the severity, the score (a small meter around the 0.5 threshold) and what happened (the reasons). A tag shows when an anomaly has been reviewed.

**Click an anomaly** to open its detail:

| Section | What it shows |
|---|---|
| Score | The score against the threshold; above 0.5 is unusual |
| Why it was flagged | The reasons, strongest first |
| This minute in numbers | Log lines, error rate, warning rate, average and p95 latency, new message types |
| Log lines from this window | Up to 10 example lines, errors first, and a link to all logs of this service in this minute on the Logs page |
| Model | The model that judged the minute |
| Alert | The alert this anomaly belongs to, with a link. LOW anomalies never open an alert |
| Your verdict | *Real problem* or *False alarm* |

Your verdict is saved for everyone; press the same button again to clear it. The verdicts are counted on the Models page. They show how often the model is right in practice.

> [!NOTE]
> If the detail says the log lines are no longer stored, the minute is older than the logs kept in Elasticsearch, or the ingestion service was not running at the time. The anomaly itself is kept in PostgreSQL.

## Alerts

Anomalies of one service that belong together, as one thing to act on. Active alerts (open and acknowledged) come first.

**Filters:** status (*Active* = open or acknowledged, *Resolved*, *All*), service and severity.

**The list** shows the alert's title, service, severity, status, and whether a Telegram message was sent.

**Click an alert** to open its detail:

- **What happened**: the title, its reasons, when it started, when its last anomaly came, how long it has been open (or how long it lasted), and the number of anomalous minutes.
- **The story**: a timeline (*Opened as high: …*, *Escalated to critical: …*, *Acknowledged by …*, *Resolved after 5 min without new anomalies*).
- **Telegram**: whether the operator was notified, and when.
- **Its anomalies**: every flagged minute that belongs to the alert, with links.
- **Respond**: type your name (it is remembered in this browser), then **Acknowledge** ("I'm looking at it") or **Resolve** ("it's fixed").

An alert that gets no new anomalies for five minutes is resolved automatically. How alerts are formed is explained in [Alerts and Telegram](alerts-and-telegram.md).

## Logs

Search the stored log lines, newest first.

- **Search messages**: full-text search in the message, for example `timeout` or `payment failed`.
- **Service** and **Level**: narrow the search, for example only `ERROR` lines of `payment-service`.
- **Refresh** loads the newest lines; the list does not change by itself.
- 100 lines per page, up to 10,000 results per search. Narrow the search to go further back.

**Click a line** to see all its fields (time, service, host, level, message, endpoint, status, latency, trace ID, event ID, metadata) and copy its event ID.

**Follow this request** shows every line with the same trace ID, as the request's path through the services: for example the gateway, then auth-service, order-service, inventory-service and payment-service for a checkout, with each step's latency and result. This is the quickest way to see *where* a failed request failed.

When you open the Logs page from an anomaly, it shows that service and that minute only; remove the time window with its ✕ to search freely again.

## Models

Which model decides what counts as an anomaly, and how well it does.

- **Active model**: its name and version, when it was trained, the algorithm, its threshold, and how many training runs and windows it learned from.
- **How it decides**: the model's settings in words.
- **How well it did**: the evaluation from training: incidents detected, minutes flagged, recall, false alarms in the fault-free run, and the results per injected fault.
- **What operators said**: the verdicts from the Anomalies page: real problems, false alarms, not yet reviewed, with a link to review the rest.
- **All versions**: every registered model; exactly one is active.

## Docs

These pages. Use the search box on the left, or the *On this page* list on the right to jump to a section. Every page can also be read on GitHub.