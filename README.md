# Crypto Open-Data Anomaly Detector

Statistical anomaly detection over CoinGecko's free public market data. A Python
detection engine flags unusual price moves, volume spikes and volatility regime
changes, and a Next.js dashboard shows them on a chart with a backtest view that
reports how many alerts would have fired historically.

**This is statistical anomaly detection, not machine learning.** There is no
trained model, no neural network, and no prediction of future prices. Every
threshold is a number a human chose and can defend. A flag means an observation
is unusual for that asset, nothing more. Nothing here is investment advice.

---

## What it does

Three classical detectors run over each asset's daily series:

| Detector | Question it answers | Default threshold |
|---|---|---|
| Rolling z-score | Is this price move large relative to the asset's own recent behaviour? | 2.0 / 3.0 / 4.0 sigma |
| Volume spike | Is today's volume large relative to its own recent average? | 2.5x the 30-day mean |
| Volatility regime | Did the asset suddenly become much more jumpy than it was? | 2.0x the 30-day norm |

Each flag is graded into a severity tier: **watch**, **notable** or **extreme**.

### The one design decision that matters

Every baseline is computed from data **strictly before** the point being scored.
The rolling window is shifted by one observation.

This is what stops the detector from cheating. If the current point were included
in its own baseline, a large move would inflate the mean and the standard
deviation and partially hide itself. That is look-ahead bias, and it makes
backtests look better than reality. It is avoided here on purpose, and there is a
test that asserts it (`test_detector_does_not_use_future_data`).

---

## Stack

- **Detection engine** — Python 3.11, FastAPI, pandas, numpy
- **Dashboard** — Next.js 14 (App Router), TypeScript, Tailwind CSS
- **Data** — CoinGecko public API, no key and no signup
- **Hosting** — Vercel free tier (Python serverless function + Next.js in one project)
- **CI** — GitHub Actions: ruff, pytest, ESLint, tsc, vitest, next build, gitleaks

No database, no paid service, no account required to run it.

---

## Run it locally

The repository is two services. Each has its own dependency file and its own
build, which is what lets Vercel build them independently.

```
backend/     FastAPI + pandas detection engine   (Python)
frontend/    Next.js dashboard                   (Node)
vercel.json  declares both services and the routing between them
```

### 1. Detection engine

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt

uvicorn main:app --reload --port 8000
```

Check it: <http://localhost:8000/health> and the interactive docs at
<http://localhost:8000/docs>.

### 2. Dashboard

```bash
cd frontend
npm install
echo 'NEXT_PUBLIC_API_BASE=http://localhost:8000' > .env.local
npm run dev
```

Open <http://localhost:3000>.

### 3. Tests

```bash
cd backend  && pytest -q            # 77 tests: detectors, backtest, digest, client, API
cd frontend && npm test             # 35 tests: formatting, filtering, CSV, API client
cd frontend && npm run lint && npm run typecheck
```

### Running both together

With the Vercel CLI installed, `vercel dev` from the repository root starts both
services on one port and applies the routing from `vercel.json`, which is the
closest local equivalent of the deployed arrangement.

---

## API

All endpoints are read-only and unauthenticated. Routes work both with and
without an `/api` prefix, so the same app runs under `uvicorn` locally and as a
Vercel function.

| Endpoint | Purpose |
|---|---|
| `GET /health` | Liveness, cache occupancy, rate-limit setting |
| `GET /config` | The detector thresholds currently in force |
| `GET /assets` | Tracked assets with a current market snapshot |
| `GET /anomalies` | Flagged events, filterable by `days`, `severity`, `asset`, `kind` |
| `GET /series/{coin_id}` | Price and volume series with event markers |
| `GET /backtest` | Replay over a window: how many alerts would have fired |
| `GET /digest` | Daily summary of what fired, as data and as plain text |
| `GET /compare` | Two assets side by side |
| `GET /export.csv` | Flagged events as a CSV download |

---

## The dashboard

Four tabs:

- **Dashboard** — one asset charted with anomalies marked on the timeline, plus a
  table of every flagged event across all tracked assets. Filter by asset,
  severity, detector and time window. Export the filtered set as CSV.
- **Backtest** — "if you had been watching this for 90 days, how many alerts
  would have fired?" Reports the count, the per-week rate and the severity mix
  per asset, with the full event list behind a toggle.
- **Digest** — a plain-text summary of the last 24h / 72h / 7d, with a copy button.
- **Compare** — two assets side by side, each with its own y-axis.

The chart is hand-drawn inline SVG rather than a charting library. It is one line
and a set of dots, so a dependency would cost more than it saves.

### On the backtest

The backtest is the credibility feature, and it is deliberately narrow. It
reports **how many flags fired**, which is a false-positive load measurement. It
does **not** report accuracy, precision, or profit, because the detectors make no
prediction and any such number would be invented.

---

## How many assets can this track?

**Shipped default: 8. Practical ceiling: 25.**

The arithmetic, from `engine/assets.py` and `engine/coingecko.py`:

- CoinGecko's keyless public API allows roughly **5 to 15 calls per minute**,
  varying with global load. This project assumes **10** and paces itself with a
  token bucket rather than firing requests in parallel.
- The market snapshot (`/coins/markets`) returns up to **250 coins in one call**,
  so the asset list costs one call no matter how many assets are tracked.
- The expensive endpoint is per-asset history: **one call per asset per refresh**.
  That is the binding constraint.

At 10 calls per minute, a cold refresh of N assets takes N calls. With a 15-minute
history cache, a warm instance serves repeat views without touching the API at all.

- **8 assets** — a cold refresh fits inside the first minute's budget with room to
  spare, and the dashboard stays responsive. This is the default.
- **25 assets** — the hard ceiling enforced in code (`MAX_ASSETS`). A cold refresh
  takes roughly 2.5 minutes of paced calls, which is tolerable for a background
  warm-up but slow for a first page load.
- **Beyond 25** — the free tier cannot refresh inside a useful window, so the API
  refuses rather than silently timing out.

Change the list with an environment variable, no code edit needed:

```bash
TRACKED_ASSETS=bitcoin,ethereum,solana,cardano
```

The trade-off is documented rather than hidden: more assets means a slower cold
start, not a broken app.

---

## Configuration

Every value is optional. The app runs with sensible defaults and no configuration.

| Variable | Default | Purpose |
|---|---|---|
| `NEXT_PUBLIC_API_BASE` | `/api` | Where the dashboard finds the engine (frontend) |
| `COINGECKO_CALLS_PER_MINUTE` | `10` | Rate-limit budget |
| `TRACKED_ASSETS` | 8 major assets | Comma-separated CoinGecko ids |
| `DETECTOR_WINDOW` | `30` | Price z-score lookback, in days |
| `DETECTOR_WATCH_THRESHOLD` | `2.0` | Sigma at which a flag becomes `watch` |
| `DETECTOR_NOTABLE_THRESHOLD` | `3.0` | Sigma for `notable` |
| `DETECTOR_EXTREME_THRESHOLD` | `4.0` | Sigma for `extreme` |
| `DETECTOR_VOLUME_THRESHOLD` | `2.5` | Volume ratio that fires |
| `DETECTOR_VOLATILITY_RATIO_THRESHOLD` | `2.0` | Volatility ratio that fires |
| `DETECTOR_COOLDOWN` | `3` | Days to suppress repeat flags of the same kind |
| `DETECTOR_ROBUST` | `false` | Use median/MAD instead of mean/std |

See `.env.example`.

---

## Deploy to Vercel

You connect your own Vercel account; this cannot be done for you.

A Next.js frontend and a Python backend in one repository need
[Vercel Services](https://vercel.com/docs/services), which builds each service
separately and routes between them. That is what the root `vercel.json` declares.

1. Push this repo to GitHub (already done if you are reading it there).
2. Go to <https://vercel.com/new> and **Import** the repository.
3. **Framework Preset must be `Services`**, not `Next.js`, and **Root Directory**
   must be the repository root. A project left on the Next.js preset builds the
   dashboard only and silently drops the Python service, which is exactly the
   failure mode that produced a 404 at `/api` before.
4. **Environment variables** — none are required. Optionally add
   `COINGECKO_CALLS_PER_MINUTE` or `TRACKED_ASSETS` from the table above.
5. Click **Deploy**.

`vercel.json` does three things: declares the two service roots, gives the
backend its ASGI entrypoint (`main:app`, resolving to the `app` object in
`backend/main.py`), and rewrites `/api/*` to the backend. It deliberately sets no
`runtime` key: Vercel detects the Python runtime, and a bare `"python3.12"`
string is not a valid runtime identifier. The Python version is pinned separately
in `backend/.python-version`.

If you are redeploying an existing project that is stuck on the wrong preset,
change **Settings → Build and Deployment → Framework Preset** to **Services**
before the next deploy. The routing table is built at deploy time, so a service
cannot be added to an already-live deployment without one.

To verify after deploying: `https://your-app.vercel.app/api/health` should return
`{"status":"ok",...}`. If it returns an HTML 404 page instead, the backend
service did not build — see the Framework Preset step above.

### Deploying the engine separately

If you would rather run the Python engine elsewhere (Render, Fly, a VPS), deploy
`backend/` as a normal ASGI app with `uvicorn main:app`, then set
`NEXT_PUBLIC_API_BASE` on the Vercel project to that URL. The frontend is not
welded to one hosting arrangement.

---

## Project layout

```
backend/         Python service (Vercel service root)
  main.py          FastAPI app and all endpoints
  engine/          detection logic
    detectors.py     the three detectors and severity grading
    coingecko.py     rate-limited, cached API client
    backtest.py      historical replay
    digest.py        daily summary
    config.py        thresholds, overridable by environment
    assets.py        tracked asset list and the hard ceiling
  tests/           pytest suite
  requirements.txt runtime dependencies
frontend/        Next.js service (Vercel service root)
  app/             App Router pages
  components/      chart, tables, badges, the four views, error diagnosis
  lib/             API client, types, formatting and filtering helpers
  tests/           vitest suite
vercel.json      both services and the public routing between them
```

---

## Why the frontend resolves its own API URL

`fetch('/api/assets')` is fine in a browser and fatal on the server. A Server
Component has no document, so a relative URL has nothing to resolve against and
the WHATWG parser throws `Failed to parse URL from /api/assets` before any
request is attempted.

The asset list is therefore fetched in the browser, where an origin always
exists, and `lib/api.ts` exposes `resolveUrl` for callers that do have an origin
to pass in. The client also classifies failures: a JSON error means the engine is
deployed and complaining, while an HTML response means it is not deployed at all.
Those two need opposite fixes, so the dashboard says which one it saw instead of
repeating generic advice.

## Limitations, stated plainly

- **Daily granularity.** CoinGecko's free history endpoint gives one point per day
  on the free tier. This is not an intraday detector.
- **Per-instance cache.** The TTL cache lives in the process, so each warm
  serverless instance keeps its own. A cold instance refetches. Redis would fix
  this and is not free.
- **No persistence.** Nothing is stored. Every view is computed from a live fetch,
  so there is no history of past runs and no alerting to an external channel.
- **The final day is dropped.** CoinGecko's last point is the in-progress day,
  whose volume is a running total. It is excluded so the volume detector is not
  misled by a partial day.
- **Thresholds are not tuned per asset.** A 2-sigma day means different things for
  Bitcoin and for a small-cap. Per-asset calibration would be the next real
  improvement.

---

## License

MIT. See [LICENSE](LICENSE).

Data from the [CoinGecko public API](https://www.coingecko.com/en/api).
