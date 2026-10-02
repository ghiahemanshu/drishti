# Drishti — Portfolio Intelligence & Exit Engine

A working, local, personal-use MVP for Indian equities. Consolidate holdings across broker/demat accounts, document the reason for owning each stock, evaluate deterministic rules, review the evidence, and simulate an exit across accounts.

**Simulation only.** All prices, financials, events and accounts are fictional, even where company names and ISINs are real. The snapshot clock is **1 October 2026**. There are no live broker calls, external AI calls, credentials or autonomous trading paths. The sample rule thresholds are examples, not recommendations.

## Team setup

Each teammate runs their own copy on their own computer. Everyone starts with the same fictional portfolio, but saved theses, rule changes, alerts and simulated orders stay in that person's local database. There is no shared team login or shared cloud portfolio in this MVP.

**Start here:** [Prerequisites](#1-install-the-prerequisites) → [First run](#2-clone-build-and-start) → [Check it works](#3-verify-your-setup). Developers can then use [development mode](#development-mode). See [local data](#local-data-backup-and-a-fresh-demo), [updating](#get-the-latest-team-changes), and [troubleshooting](#troubleshooting) for ongoing use.

### 1. Install the prerequisites

| Tool | Version / purpose | Installation |
|---|---|---|
| Git | Clone and update the project | [Git downloads](https://git-scm.com/downloads/) |
| Node.js and npm | Node.js **24 LTS recommended**; Node.js 22 LTS also fits the project's Vite version. npm comes with the standard Node.js installation. | [Node.js downloads](https://nodejs.org/en/download); choose your operating system and an LTS version |
| Python | **3.11 or newer**; runs the API and includes SQLite | [Python downloads](https://www.python.org/downloads/); Windows setup help: [official guide](https://docs.python.org/3/using/windows.html) |
| Browser | A current Chrome, Edge, Firefox or Safari release | Use your usual browser |

The Node.js recommendation follows the [official release support schedule](https://nodejs.org/en/about/previous-releases). You do not need Docker, a separate database server, a Python virtual environment, `pip install`, an `.env` file, API keys, or broker credentials for this demo.

On macOS, use Terminal; on Linux, use your terminal; on Windows, use PowerShell. Install the tools, then **close and reopen your terminal** so it sees the new programs. Internet access is needed to clone the repository and download npm packages. Once built, the mock app runs locally without external market-data services.

Check the installations before continuing.

**macOS / Linux:**

```sh
git --version
node --version
npm --version
python3 --version
```

**Windows PowerShell:**

```powershell
git --version
node --version
npm.cmd --version
py -3 --version
```

Confirm Python reports 3.11 or later. If Windows has `python` but not `py`, check `python --version` and use `python` in place of `py -3` throughout these instructions. Windows examples use `npm.cmd` so they do not depend on PowerShell allowing the `npm.ps1` script.

### 2. Clone, build and start

Choose a writable working folder on your own computer. Run **one** of the following sequences, according to your operating system. Run each command only after the previous one succeeds.

**macOS / Linux:**

```sh
git clone https://github.com/ghiahemanshu/drishti.git
cd drishti
npm ci
npm run build
python3 -m backend.server
```

**Windows PowerShell:**

```powershell
git clone https://github.com/ghiahemanshu/drishti.git
cd drishti
npm.cmd ci
npm.cmd run build
py -3 -m backend.server
```

The public repository can be cloned without a GitHub account. `npm ci` installs the exact dependency versions from `package-lock.json`. `npm run build` checks TypeScript and creates the frontend in `dist/`; that generated folder is not stored in GitHub. Python creates and seeds `data/portfolio.sqlite` automatically on first startup. There is no separate database setup or migration command.

All commands after `cd drishti` must run from the repository root: the folder containing `package.json`, `backend/`, `frontend/`, and `data/`. Do not start the server from inside `backend/` or by opening `index.html` directly.

A successful startup prints:

```text
Drishti simulation ready: http://127.0.0.1:8765
Fictional data only. No live broker calls. Re-evaluates every 60 seconds.
```

Open **[http://127.0.0.1:8765/](http://127.0.0.1:8765/)** in your browser. Leave the terminal open while using the app. Press **Ctrl+C** in that terminal to stop it. Closing the browser alone does not stop the server.

### 3. Verify your setup

On a fresh database, the dashboard should show:

- **8 stocks**, **3 mock accounts**, and equity value **₹51,62,980**.
- **10 enabled rules** and **20 active alerts** from the fictional snapshot.
- **Simulation mode / Demo data**, dated **1 October 2026**. The snapshot date is intentionally fixed and is not today's live market data.

Visit **[http://127.0.0.1:8765/api/health](http://127.0.0.1:8765/api/health)**. The response should be:

```json
{"ok": true, "mode": "simulation"}
```

If you have already changed rules or simulated an exit, your counts and values will differ; that is expected. For a guided tour, continue to [Try this first](#try-this-first).

## Everyday startup and shutdown

You only need to install dependencies and build on first setup or after relevant code changes. For normal use, open a terminal, change into your existing `drishti` folder, and run:

| Operating system | Start the app | Stop the app |
|---|---|---|
| macOS / Linux | `python3 -m backend.server` | Ctrl+C in the server terminal |
| Windows | `py -3 -m backend.server` | Ctrl+C in the server terminal |

Open [http://127.0.0.1:8765/](http://127.0.0.1:8765/) after startup. Saved work returns from the same database. There is no background service: scans stop when the server is stopped or the computer is asleep.

On macOS, you can also double-click **`Start.command`** in Finder, or run `sh Start.command` from the repository root. It starts the backend and, if the frontend build is missing, installs dependencies and builds it first. It does **not** rebuild an existing `dist/` after a Git update; follow the update instructions below. The script does not automatically open a browser. Windows users should use the commands above; `npm start` and `npm test` currently call `python3`, which may not exist under that name on Windows.

The separately supplied portable ZIP contains a prebuilt frontend and needs only Python to run. GitHub's **Code → Download ZIP** is a source archive and still requires the npm install/build steps. Use a Git clone for normal team development so updates and branches work.

## Development mode

Use this mode when editing the frontend. Open **two terminals in the repository root**; both must remain running.

**Terminal 1 — backend:**

```sh
# macOS / Linux
python3 -m backend.server
```

```powershell
# Windows PowerShell
py -3 -m backend.server
```

**Terminal 2 — frontend:**

```sh
# macOS / Linux
npm run dev
```

```powershell
# Windows PowerShell
npm.cmd run dev
```

Open **[http://127.0.0.1:5173/](http://127.0.0.1:5173/)** for development. Vite refreshes the page when frontend files change and forwards `/api` requests to the Python backend on port **8765**. Restart the Python server after editing backend files; it does not auto-reload.

| URL | Purpose |
|---|---|
| `http://127.0.0.1:5173/` | Frontend development server with hot reload |
| `http://127.0.0.1:8765/` | Last production build, served by Python |
| `http://127.0.0.1:8765/api/health` | Backend health check |

Keep these default ports in development. If you change the API port, also update the `/api` proxy target in `vite.config.js` and restart Vite. Changing Vite's port also requires updating the allowed browser origins in `backend/server.py`; otherwise writes will be rejected. The [port-conflict workaround](#troubleshooting) uses the production build to avoid those extra changes.

## Local data, backup and a fresh demo

| Location | Contents | Commit to Git? |
|---|---|---|
| `data/seed.json` | Shared fictional starting portfolio | Yes; intentional fixture changes only |
| `data/portfolio.sqlite` | Your saved local portfolio and audit history | No; ignored |
| Other `*.sqlite` files and SQLite `-wal` / `-shm` companions | Local test/demo state | No; ignored |
| `node_modules/`, `dist/`, Python caches and `.env` files | Generated files or local settings | No; ignored |

Each teammate has an independent database. A Git pull updates code and fixtures; it does not copy another teammate's holdings or reset your existing database. Use a local disk for runtime data rather than a shared network folder or a cloud-synced working directory.

**Back up your work:** stop every backend process using that database with Ctrl+C, then copy the entire `data/` folder to a separately named, dated backup folder using your file manager. Include any SQLite companion files that are present. Do not copy only a live SQLite database file while the server is writing to it. Keep backups outside commits.

**Start a fresh demo without deleting anything:** stop the server, then use a new filename in the existing `data/` folder:

```sh
# macOS / Linux
python3 -m backend.server --db data/team-demo-02.sqlite
```

```powershell
# Windows PowerShell
py -3 -m backend.server --db data/team-demo-02.sqlite
```

The named database is seeded only if it is new. Reusing a filename reopens its saved state. To return to your original portfolio, stop this instance and run the normal startup command without `--db`. If you choose a different parent directory, create it first; the app does not create database parent folders.

To restore a backup, stop the server, copy the backed-up data folder into a separate local folder, keep its database and companion files together, and start with `--db` pointing to that database. Keep the current database until you have checked the restored copy.

For an isolated development session, start Terminal 1 with `--db data/development.sqlite`. The frontend always uses whichever database its running backend selected.

## Get the latest team changes

Stop your local servers and back up any demo state you want to keep. From the repository root, inspect your working copy first:

```sh
git status --short
```

If this lists edited or untracked source files, preserve your work on a branch before updating; do not discard it to make the update proceed. For a clean working copy:

```sh
git switch main
git pull --ff-only
```

Then rebuild and restart.

**macOS / Linux:**

```sh
npm ci
npm run build
python3 -m backend.server
```

**Windows PowerShell:**

```powershell
npm.cmd ci
npm.cmd run build
py -3 -m backend.server
```

Reload the browser after restarting. If a future release changes database compatibility, check that release's instructions before reusing existing state; this MVP has no general migration framework. A new demo database is available as a fallback without deleting the previous one.

## Contributing as a team

Use a feature branch for code or documentation changes:

```sh
git switch main
git pull --ff-only
git switch -c your-name/short-description
```

Run the [validation commands](#validation) before sharing code changes. Stage only the intended source files, commit them, push your branch, and open a pull request into `main`. Push access requires a GitHub account with repository write access, or a fork; the repository owner must grant access if needed. Cloning and running the public demo do not require write access.

```sh
git status --short
git add path/to/changed-file
git commit -m "Describe the change"
git push -u origin your-name/short-description
```

Replace the branch and file names above with your own. Keep `package-lock.json` committed when intentionally changing dependencies. Do not commit local databases, credentials, or real portfolio data. If pushing asks for a password or reports permission denied, set up your authorised GitHub SSH/credential-manager connection or ask the repository owner for access; do not paste tokens into source files or the README.

## Troubleshooting

| Symptom | What to do |
|---|---|
| `git`, `node`, `npm`, `python3` or `py` is not found | Install the missing prerequisite, reopen the terminal, and repeat the version checks. On Windows, use `python` if it reports Python 3.11+ and `py` is unavailable. |
| Windows says `npm.ps1 cannot be loaded` | Use the documented `npm.cmd` commands; changing PowerShell's execution policy is not needed. |
| `npm ci` fails on a network/proxy error | Check access to the npm registry through your organisation's approved network/proxy, then rerun `npm ci`. Keep the committed lockfile. |
| `npm ci` reports the lockfile is out of sync | Confirm you are on the intended branch with matching `package.json` and `package-lock.json`; ask the author to commit the correct lockfile. Do not delete it just to make installation pass. |
| `No module named backend` | Change to the repository root and run `python3 -m backend.server` or `py -3 -m backend.server`. |
| `Frontend build missing` / HTTP 503 | Run `npm ci` and `npm run build` (Windows: `npm.cmd ci` and `npm.cmd run build`) from the repository root, then refresh. |
| `Address already in use` on 8765 | Stop your earlier Drishti instance with Ctrl+C. Alternatively, run `python3 -m backend.server --port 8770` (Windows: `py -3 -m backend.server --port 8770`) and open `http://127.0.0.1:8770/`. Use the built app for this workaround. |
| Vite reports port 5173 is already in use | Stop your earlier frontend terminal or use the built app on 8765. Vite uses `strictPort` and will not silently choose another port. |
| Cannot reach the app / development UI cannot load data | Confirm the backend terminal is still running and the health URL responds. In development, both terminals must run and the proxy must point to the API port. |
| “Refresh the app before making changes” | Reload the browser after restarting the backend; the session token changes on every restart. |
| “Request origin is not allowed” | Use the documented `127.0.0.1` or `localhost` URLs and default development ports. Custom dev ports require matching backend origin configuration. |
| `unable to open database file` / `database is locked` | Check that the database's parent folder exists and is writable. Keep it on a local disk and stop extra backend processes or database editors before retrying. |
| `Start.command` does not launch from Finder | Use `sh Start.command` in Terminal, or use the manual setup/start sequence. Only use this launcher on macOS/Linux. |
| UI still looks old after pulling changes | Run the build again, restart the backend, and reload. `Start.command` does not refresh an already-existing build. |
| Editing `seed.json` does not change the dashboard | Existing state is intentionally preserved. Start with a new `--db` filename to load the changed fixtures. |
| A teammate cannot open the URL from another computer | `127.0.0.1` points to each person's own machine. Each teammate must run their own copy; this is not a shared hosted service. |

When reporting a setup issue, include your OS, the version-check output, current branch/commit (`git rev-parse --short HEAD`), the command you ran, and its error text. Include browser/server errors if relevant. Leave credentials and personal portfolio information out of the report.

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

See [Local data, backup and a fresh demo](#local-data-backup-and-a-fresh-demo) for persistence and reset instructions.

To regenerate fictional fixtures, run `python3 -m backend.make_seed` (Windows: `py -3 -m backend.make_seed`). This rewrites the tracked `data/seed.json`; it does not change an existing database. Review and commit fixture changes only when the team should share a new starting portfolio. Any number of account records and holdings can be supplied. Account IDs identify broker trading connections; demat references remain separate metadata. Use one holding row per account/ISIN, with pledged, blocked and unsettled quantities represented as disjoint buckets.

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

Run these from the repository root; the backend does not need to be running.

**macOS / Linux:**

```sh
python3 -m unittest discover -s tests -v
npm run build
```

**Windows PowerShell:**

```powershell
py -3 -m unittest discover -s tests -v
npm.cmd run build
```

`npm test` is also available wherever `python3` resolves correctly. The current suite contains **36 tests** and should finish with `OK`. The build should finish successfully after the TypeScript check and write `dist/index.html` plus its assets.

Tests use temporary databases. Coverage includes all DMA calculations, completed-week semantics, consecutive observations, no lookahead, stale/missing data, quarter gaps, volume denominator, crossovers, event windows, ISIN consolidation, alert deduplication, rule version conflicts, append-only audit, persistence, restricted quantities, proportional rounding, explicit confirmation, expiring/stale previews, concurrent confirmations, replay after restart, untrusted order-field overrides and multi-account rollback.

The onboarding workflow was checked from a fresh GitHub clone on **2 October 2026 on macOS**: dependency installation, all **36 automated tests**, the TypeScript check, production build, server startup, health endpoint, built assets and the expected seeded portfolio values passed. The check used a separate database and port. Windows and Linux commands are provided above; they have not been verified on those operating systems in this workspace.

Earlier local HTTP smoke checks verified missing-token, disallowed-origin/Host and invalid-confirmation rejection. Both browser agent tools were validated with valid and invalid inputs.

Browser walkthroughs exercise the dashboard, thesis save, rule creation, evidence review, account allocations, simulated confirmation receipt, and smaller-screen layout using a separate QA database. The default demo database is kept free of test orders.

## Optional browser agent tools

When the browser supports WebMCP, the app registers `read_portfolio_intelligence` (read-only, excludes session tokens) and `start_alert_review` (opens the same review dialog). Neither tool places an order or bypasses confirmation. Browsers without this API retain the complete UI.

## Moving beyond the prototype

Implement real providers behind `HoldingsAdapter`, `MarketDataAdapter`, and `ExecutionAdapter`. Preserve normalized ISINs and account provenance. Real holdings may overlap broker-reported balance categories: normalize into **disjoint** unavailable buckets rather than subtracting overlapping fields twice.

Reference contracts: [Kite portfolio API](https://kite.trade/docs/connect/v3/portfolio/) and [Kite order API](https://kite.trade/docs/connect/v3/orders/). These are references for future adapter work; no Kite integration is claimed here.

Before live use: licensed market/fundamental sources, exchange calendars, corporate-action adjustment, provider timestamps and provenance, reconciliation, secret storage, authentication, authorisation, broker-specific settlement approval, exchange restrictions/circuits, real order types, costs, liquidity controls and operational monitoring are needed. The adapters are deliberately mock-only until those contracts are implemented and verified.

The local audit prevents accidental modification through the application and ordinary SQL UPDATE/DELETE; a user with filesystem access can replace the database. It is not a compliance-grade tamper-proof ledger. No multi-user tenancy, remote notifications, live order execution, tax-lot accounting, import UI or deployment is included.
