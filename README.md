# Drishti — Portfolio Intelligence & Exit Engine

A working, local, personal-use MVP for Indian equities. Consolidate holdings across broker/demat accounts, document the reason for owning each stock, evaluate deterministic rules, review the evidence, and simulate an exit across accounts.

**Simulation only.** All prices, financials, events and accounts are fictional, even where company names and ISINs are real. The snapshot clock is **1 October 2026**. There are no live broker calls, external AI calls, credentials or autonomous trading paths. The sample rule thresholds are examples, not recommendations.

## Run it

Requirements: **Python 3.11+**, **Node.js 20+** and **npm**. No Python packages or broker credentials are needed.

```sh
git clone https://github.com/ghiahemanshu/drishti.git
cd drishti
npm ci
npm run build
npm start
```

Open **http://127.0.0.1:8765/**. Keep the terminal running; Ctrl+C stops the app. If the port is occupied, use `python3 -m backend.server --port 8770` and open that port.

After building once, run `python3 -m backend.server` to reopen the app. On macOS you can also double-click `Start.command`; it installs and builds the frontend if needed. The separately supplied portable ZIP already contains the built frontend and needs only Python to run.

Development (two terminals):

```sh
# Terminal 1: API and monitoring worker
npm start
# Terminal 2: frontend with hot reload, API proxy to port 8765
npm run dev
```

Open http://127.0.0.1:5173/ for development. The backend serves the production build on port 8765. No Python packages need to be installed.

## Try this first

1. Open **TCS** in Holdings. Inspect its technical indicators, account breakdown, fundamentals and thesis.
2. On **Thesis**, change the investment thesis and save it.
3. Open **Two closes below 200 DMA** from the stock’s alerts. Evidence shows the actual close and the independently calculated MA for each observation.
4. Select **Exit 50%**, choose the accounts, then **Preview exit**.
5. Review whole-share allocation and excluded shares. **Confirm simulated exit** is the only action that changes the demo holdings. The receipt appears in Orders; all evidence is retained in Audit trail.
6. In **Exit rules**, create/edit/disable a rule. Try revenue growth below 10% for two quarters; a 50 DMA / 200 DMA crossover; or an AND group combining a price breakdown and volume ratio. Change scope to **Portfolio risk** for concentration rules.

The initial demo contains eight securities, three broker accounts, 13 account/security holding rows, 330 synthetic weekday bars per stock, four published quarters, ten rules and seeded breaches. TCS has 240 shares, of which 235 are sellable. Its simulated 50% exit allocates 120 shares across the three accounts. Suzlon demonstrates pledged and blocked holdings. Some bank ratios are intentionally unavailable.

## What is implemented

- **ISIN consolidation** with weighted acquisition cost, unrealised P&L, current value, equity weight and account-level balances. Pledged, blocked and unsettled quantities remain visible.
- **Thesis persistence** per stock.
- **Rule builder**: stock-specific or all-stock rules; portfolio rules; nested AND/OR; thresholds or compatible metric comparisons; 1–8 consecutive periods; enable/disable; optimistic version checks; five alert severities.
- **Technicals**: 20/50/100/200-day simple moving averages; completed weekly close and 40-week simple MA; crosses-above/below; 252-session closing-high drawdown; volume versus the preceding 20 sessions; composites.
- **Fundamentals**: revenue growth and absolute sales; EBITDA margin and QoQ change in basis points; PAT growth; ROCE/ROE; debt/equity; net debt/EBITDA; interest coverage; CFO/PAT, CFO and FCF; promoter holding, QoQ holding change and pledge.
- **Events**: auditor or management resignation, rating downgrade, regulatory action, related-party transaction, acquisition, capital raise and guidance cut, using a 90-calendar-day lookback.
- **Portfolio risk**: largest company, largest sector, small-cap exposure, below-200-DMA equity exposure, equity in warning/exit states and cash allocation.
- **Alert lifecycle**: active, reviewed and resolved history; structured explanation with values, observation dates, threshold, comparator, period count and data-gap reasons. Reviewed means acknowledged, not resolved.
- **Confirmed mock exits** with 25/50/100% presets, selected accounts, proportional allocation, five-minute previews, transaction rollback, quantity revalidation and duplicate protection.
- **Audit log** for initialisation, triggered/resolved alerts, rule versions, thesis changes, review acknowledgements, scans, order previews and confirmed exits. SQLite triggers reject UPDATE/DELETE of audit entries. UI shows the newest 250 entries and exports those entries as JSON; the database retains all events.
- **Monitoring while running**: the backend re-evaluates the snapshot every 60 seconds. Manual scans are available. The browser refreshes state every 60 seconds. This does not fetch new market data or send email/WhatsApp notifications.

## Stack and code map

React 19 + TypeScript + Vite 6, Lucide icons, plain CSS; Python standard-library HTTP server; SQLite in WAL mode. SQLite allows reliable local persistence and serialised write transactions without another service. The HTTP server is deliberately a local prototype host, not a production deployment server.

```text
backend/
  engine.py        Pure indicator functions, validation and three-valued rules
  adapters.py      Holdings, market-data and execution protocols + mocks
  store.py         SQLite transactions, application service, alerts and exits
  server.py        Loopback API, background scan and static frontend host
  make_seed.py     Reproducible synthetic data generator
frontend/
  App.tsx          Dashboard and application navigation
  RuleEditor.tsx   Nested rule builder
  StockDetail.tsx  Position, indicators, thesis and rule evaluation detail
  ExitFlow.tsx     Review → preview → explicit confirmation → receipt
  Views.tsx        Alerts, rules, orders, connections and audit
  components.tsx   Accessible native dialogs, evidence and sparklines
  api.ts           Typed client helpers and INR formatting
  styles.css       Responsive layout and styling
 data/seed.json    Human-readable, deterministic fixtures
 tests/           Indicator, lifecycle, persistence and execution tests
```

Runtime state is in `data/portfolio.sqlite` (ignored by Git). The database is created from `seed.json` only on the first start. Edits to seed data do not overwrite an existing portfolio.

For a **fresh demo without deleting current work**, stop the server and start it with a new database path:

```sh
python3 -m backend.server --db data/another-demo.sqlite
```

To regenerate fixtures from the generator: `python3 -m backend.make_seed`. To customise the initial portfolio, edit the generated JSON before starting with a new database. Any number of account records and holdings can be supplied. Account IDs identify broker trading connections; demat references are separate account metadata. One holding row per account/ISIN is expected, with pledged, blocked and unsettled quantities represented as disjoint buckets.

## Deterministic rule semantics

A leaf condition looks like:

```json
{"metric":"close","op":"lt","rhsMetric":"dma200","periods":2}
```

A composite uses `all` or `any`:

```json
{
  "all": [
    {"metric":"revenue_growth","op":"lt","value":10,"periods":2},
    {"metric":"close","op":"lt","rhsMetric":"dma200","periods":1},
    {"metric":"volume_ratio","op":"gt","value":1.5,"periods":1}
  ]
}
```

Rules contain `name`, `scope` (`stock`/`portfolio`), `isin` (`*` for all), `severity`, `enabled`, and `condition`. Existing-rule updates must include the current `id` and `version`. Maximum depth is four and maximum node count is 30. The metric catalog is returned by `/api/state` and defined in `engine.py`.

- MAs include the observation’s completed close. Each historical observation uses its own historical MA. Comparisons use full precision; display values are rounded.
- Crossover is an event: prior value must be on the other side or equal, and current value strictly beyond the reference. Consecutive-period crossover rules require a crossover on **each** requested period; normally use one period.
- Volume ratio excludes the signal session from its 20-session baseline. Drawdown is a positive percentage below the maximum **closing** price in the last 252 sessions, including today. It is not an intraday-high stop.
- Weekly values use the last available completed bar in ISO weeks whose Friday is no later than the snapshot date. Current partial weeks are excluded. The fixture generator excludes weekends but does **not** model exchange holidays. A real adapter must supply exchange-calendar-aware, completed, split-adjusted histories and reliable corporate-action handling. Weekly holiday completion requires that calendar as well.
- Fundamental thresholds use normalized published values, not scraped text. Reports published after the evaluation date are excluded. Consecutive-quarter rules require adjacent quarter identifiers; missing quarters produce unknown. CFO/PAT, CFO and FCF in the fixtures are TTM. Revenue growth is YoY; margin and promoter-holding changes are QoQ.
- Missing/insufficient data is `null` (unknown). Unknown is never silently converted to zero or healthy. AND/OR follow three-valued logic: `false AND unknown = false`; `true OR unknown = true`; otherwise an unresolved input propagates unknown. Existing active alerts remain active with a data gap when evaluation becomes unknown; exits from those alerts are blocked.
- Technical data older than seven calendar days and the latest fundamentals older than 180 days are unknown **relative to the snapshot clock**. These are demo policies, not exchange calendars. Stale valuation fallback is labelled and affected exits are blocked.
- Concentration and risk exposure use equity market value as denominator; cash allocation uses equity plus simulated cash. No derivative exposure, portfolio drawdown, covariance or benchmark analytics is implemented.
- Severity is user-configured. Even `hard_exit` only generates an alert. There is no autonomous execution path.
- Repeated scans reuse an active alert for `(rule ID, version, target)`. A clear result resolves it; a later breach starts a new episode. Updating a rule preserves the old alert and creates a new rule version. Audit captures original trigger evidence; the active alert’s displayed evidence is refreshed on scans.

## Exit invariants

1. An active, evaluable **stock alert** is required to prepare a preview. Portfolio alerts do not directly sell a basket.
2. Desired shares = `floor(selected held quantity × percentage / 100)`. Executable shares = minimum of desired and total selected sellable quantity. A 100% exit may leave restricted shares behind; the preview explicitly shows this.
3. Allocation is proportional to sellable quantities, using largest-remainder rounding with account-ID tie breaking. Quantities are nonnegative integers and never exceed a lot’s availability.
4. Creating a preview cannot submit an order. Client-supplied prices/quantities on confirmation are ignored: the server uses its persisted preview.
5. Confirmation requires `confirmed: true`, an unexpired preview and an idempotency key. Holdings/rule revision changes invalidate outstanding previews. Availability and alert status are rechecked inside the same `BEGIN IMMEDIATE` transaction.
6. A unique preview and a unique idempotency key protect against double clicks, concurrent duplicate requests and retries after process restart. A competing preview from the previous revision cannot fill after the first exit changes holdings. A new, deliberately confirmed preview can reduce the remaining position again.
7. Mock fills, holdings, cash, order receipts and the audit entry commit atomically. Failures roll back. Mock market orders immediately fill at the fixed snapshot close, without taxes, fees or slippage.
8. This SQLite transaction model is appropriate for mocks. **It does not make external broker calls atomic.** Real execution requires a durable order-intent/outbox design, per-leg idempotency, broker-side client references where supported, timeout reconciliation, partial-fill handling and recovery before any retries.

## API

`GET /api/state` provides the consolidated portfolio, catalog, rules, evaluations, alerts, orders, audit and a session token. Use `X-Session-Token` and `Content-Type: application/json` for writes. GET responses have no CORS access; writes reject untrusted origins and Host headers. The server binds only to `127.0.0.1`. This is request-forgery protection for a local app, **not user authentication**. Do not expose it publicly or use it for multiple users.

| Method | Route | Body / purpose |
|---|---|---|
| GET | `/api/health` | Service status and simulation mode |
| GET | `/api/state` | App state + session token |
| GET | `/api/security/{isin}` | Raw fixture histories, fundamentals and events |
| POST | `/api/scan` | `{}`; re-evaluate the frozen dataset |
| POST | `/api/rules` | Validated rule definition; create or versioned update |
| POST | `/api/thesis` | `{ "isin": "…", "body": "…" }` |
| POST | `/api/alerts/review` | `{ "alertId": "…" }` |
| POST | `/api/orders/preview` | `{ "alertId": "…", "percent": 50, "accountIds": ["zerodha"] }` |
| POST | `/api/orders/confirm` | `{ "previewId": "…", "idempotencyKey": "unique-key", "confirmed": true }` |

## Validation

```sh
npm test          # Python standard-library unit/integration suite
npm run build    # TypeScript checks + production frontend build
```

Tests use temporary databases. Coverage includes all DMA calculations, completed-week semantics, consecutive observations, no lookahead, stale/missing data, quarter gaps, volume denominator, crossovers, event windows, ISIN consolidation, alert deduplication, rule version conflicts, append-only audit, persistence, restricted quantities, proportional rounding, explicit confirmation, expiring/stale previews, concurrent confirmations, replay after restart, untrusted order-field overrides and multi-account rollback.

All **36 automated tests passed**, as did the TypeScript check and production build. Local HTTP smoke checks verified missing-token, disallowed-origin/Host and invalid-confirmation rejection. Both browser agent tools were validated with valid and invalid inputs.

Browser walkthroughs exercise the dashboard, thesis save, rule creation, evidence review, account allocations, simulated confirmation receipt, and smaller-screen layout using a separate QA database. The default demo database is kept free of test orders.

## Optional browser agent tools

When the browser supports WebMCP, the app registers `read_portfolio_intelligence` (read-only, excludes session tokens) and `start_alert_review` (opens the same review dialog). Neither tool places an order or bypasses confirmation. Browsers without this API retain the complete UI.

## Moving beyond the prototype

Implement real providers behind `HoldingsAdapter`, `MarketDataAdapter`, and `ExecutionAdapter`. Preserve normalized ISINs and account provenance. Real holdings may overlap broker-reported balance categories: normalize into **disjoint** unavailable buckets rather than subtracting overlapping fields twice.

Reference contracts: [Kite portfolio API](https://kite.trade/docs/connect/v3/portfolio/) and [Kite order API](https://kite.trade/docs/connect/v3/orders/). These are references for future adapter work; no Kite integration is claimed here.

Before live use: licensed market/fundamental sources, exchange calendars, corporate-action adjustment, provider timestamps and provenance, reconciliation, secret storage, authentication, authorisation, broker-specific settlement approval, exchange restrictions/circuits, real order types, costs, liquidity controls and operational monitoring are needed. The adapters are deliberately mock-only until those contracts are implemented and verified.

The local audit prevents accidental modification through the application and ordinary SQL UPDATE/DELETE; a user with filesystem access can replace the database. It is not a compliance-grade tamper-proof ledger. No multi-user tenancy, remote notifications, live order execution, tax-lot accounting, import UI or deployment is included.
