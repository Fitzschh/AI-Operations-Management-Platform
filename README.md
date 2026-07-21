# E-Menu Portal

*by **Touch** — the restaurant-facing product of the **TouchOrders** ordering platform.*

**AI operations intelligence for restaurants.** E-Menu Portal turns a café's live order data into
plain-language operational advice — an AI analyst that watches the numbers, spots what matters, and
tells the owner what to do next, instead of another dashboard they have to interpret themselves.
Deterministic analytics compute the facts; OpenAI explains them. The AI never invents a number.

---

## Problem

Small restaurant owners are drowning in operational data and starved of operational *insight*. A
typical café owner:

- Sees dashboards full of charts but has no time to interpret them mid-service.
- Reacts to stockouts and slow hours *after* they cost money, not before.
- Can't afford a full-time business analyst or operations manager.
- Gets generic advice from tools that don't know *their* menu, *their* peak hours, or *their* numbers.

They don't need more data. They need someone to read the data for them and say, in plain words,
"here's what happened, why, and what to do."

---

## Solution

E-Menu Portal is that someone — a lightweight AI operations analyst layered over the café's existing
Firebase data. It observes real orders, analyzes them with deterministic Python/JS math, and asks
OpenAI to **explain and recommend** in the voice of an experienced operations consultant.

The guiding philosophy: **Observe → Analyze → Recommend → Explain** — proactive intelligence, not a
passive dashboard. Every statistic is computed deterministically before the AI ever sees it, so the
AI only interprets real figures and can never fabricate one.

---

## Core Features

- **AI Operations Dashboard** — animated KPIs, deltas vs. yesterday/last week, a Business Health
  score, and live AI commentary that interprets rather than repeats the numbers.
- **Live Restaurant Analytics** — Today / 7d / 30d / 12-month periods, interactive dependency-free
  SVG charts (area, bar, donut, hourly heat-strip), category mix, and a statistical overview.
- **AI Shift Handoff (Daily Business Brief)** — a once-per-day briefing generated on login and
  cached for the day: yesterday's revenue, top and fastest-growing products, inventory risks, one
  operational insight, and the most important action for the shift.
- **Executive Presentation Generator** — a full-screen, scene-by-scene board-meeting briefing
  narrated by the AI (today vs. yesterday, weekly momentum, product movers, risks, forecast, action
  plan).
- **Revenue Leak Detection** — surfaces likely missed revenue (stockout losses, peak-hour
  bottlenecks, slow movers) grounded in the café's own sales and inventory data.
- **AI Chat Assistant** — an "Ask AI Analyst" drawer with conversational memory: ask a question,
  then follow up naturally ("what about yesterday?", "what should I do?"). Strictly scoped to
  restaurant operations.
- **Inventory Monitoring** — health score, predicted shortages ("~2 days left at current pace"),
  urgency sorting, thresholds, and adjustment history.
- **Sales Analytics** — deterministic revenue, order, AOV, and product-performance metrics computed
  client-side from the live database.
- **Smart Recommendations** — instant, deterministic recommendations (problem → evidence → impact →
  confidence), each with a **"Why?"** button that calls the AI to explain *that specific*
  recommendation using only the already-computed figures.

---

## AI Workflow

```
Restaurant data (orders, sales, inventory)
        │
        ▼
Firebase Realtime Database        ← single source of truth for all operational data
        │
        ▼
Deterministic analytics (client)  ← metrics, patterns, forecasts, recommendations
        │
        ▼
FastAPI AI Gateway (Railway)      ← verifies the Firebase ID token, holds the OpenAI key,
        │                            forwards the request, returns the response — nothing else
        ▼
OpenAI (gpt-4o-mini)              ← explains the computed analytics and writes recommendations
        │
        ▼
Insights (structured JSON)
        │
        ▼
Restaurant owner
```

Key properties:

- **Firebase stores all operational data.** Orders, sales, inventory, and menus live only in the
  Realtime Database.
- **FastAPI is only an authenticated AI gateway.** It verifies the Firebase ID token, holds the
  OpenAI API key, forwards the request, and returns the answer.
- **OpenAI performs the analysis** — interpretation, recommendations, and narrative, never the
  arithmetic.
- **Operational data never lives inside the backend.** The gateway is stateless: no database, no
  mirrors, no restaurant records. It reads nothing from Firebase except the token it verifies.

---

## Architecture

```
                Tablet / Dashboard (React + Vite)
                          │
          ┌───────────────┼───────────────┐
          │               │               │
          ▼               ▼               ▼
   Firebase Auth   Realtime Database   FastAPI (Railway)
   (identity)      (operational data)  (authenticated AI gateway)
                                              │
                                              ▼
                                        OpenAI (gpt-4o-mini)
```

The frontend talks to Firebase directly for authentication and data, and to FastAPI **only** for
AI. The backend is intentionally minimal — a secure key holder and request forwarder — so the OpenAI
key never reaches the browser.

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | React 18, Vite, React Router, Lucide icons, dependency-free SVG charts |
| **Backend** | FastAPI + Uvicorn (Python 3.12), `firebase-admin` (token verification), OpenAI SDK |
| **Database** | Firebase Realtime Database |
| **Authentication** | Firebase Authentication (email/password → ID tokens verified server-side) |
| **Hosting** | Firebase Hosting (frontend) · Railway (backend) |
| **AI** | OpenAI Chat Completions — `gpt-4o-mini` |

---

## Screenshots

> _Add screenshots before submission._

| Dashboard | AI Analyst Chat | Executive Presentation |
|---|---|---|
| _`docs/screenshots/dashboard.png`_ | _`docs/screenshots/ai-chat.png`_ | _`docs/screenshots/executive.png`_ |

| Analytics | Inventory | Smart Recommendations |
|---|---|---|
| _`docs/screenshots/analytics.png`_ | _`docs/screenshots/inventory.png`_ | _`docs/screenshots/recommendations.png`_ |

---

## Demo

> 🎥 **Demo video:** _add YouTube link before submission._

---

## Pilot Testing

E-Menu Portal was validated in a **real restaurant pilot** at *Sugar Cafe Nivel Hills*, running against
live order and inventory data in the same Firebase project the platform uses in production. The pilot
informed the cost model (the AI is designed to stay a small fraction of a café's subscription) and
the "AI never invents numbers" honesty rules enforced throughout the UI.

> _No performance statistics are claimed here; the pilot validated real-world usage and workflow fit._

---

## Installation

### Prerequisites
- Node.js 18+ and npm
- Python 3.12
- A Firebase project (Authentication + Realtime Database) and an OpenAI API key

### Frontend

```bash
npm install
npm run dev      # local dev server (http://localhost:5173)
npm run build    # production build → dist/
firebase deploy --only hosting   # deploy dist/ to Firebase Hosting
```

### Backend (AI gateway)

```bash
cd agent-core
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn --app-dir src touchorders_core.main:app --reload   # local
# production start command (Railway): see agent-core/railway.toml
```

### Environment variables

**Frontend** (`.env`, exposed to the browser — non-secret):

```
VITE_API_BASE_URL=https://<your-backend>.up.railway.app   # backend origin
VITE_FIREBASE_API_KEY=...
VITE_FIREBASE_AUTH_DOMAIN=...
VITE_FIREBASE_DATABASE_URL=...
VITE_FIREBASE_PROJECT_ID=...
VITE_FIREBASE_APP_ID=...
```

**Backend** (Railway Variables — secret; never in the repo). See
[`agent-core/.env.example`](agent-core/.env.example) and
[`agent-core/docs/deployment/railway-secrets.md`](agent-core/docs/deployment/railway-secrets.md):

```
OPENAI_API_KEY=sk-...                    # the only OpenAI key holder
FIREBASE_SERVICE_ACCOUNT_JSON={...}      # used only for verify_id_token
```

Full step-by-step deployment: [`DEPLOYMENT.md`](DEPLOYMENT.md).

---

## Repository Structure

```
.
├── src/                      # React frontend
│   ├── config/               # branch/role access map
│   ├── context/              # Auth, Theme, BranchData, LiveAnalystProvider
│   ├── hooks/                # deterministic analytics + inventory processors
│   ├── lib/                  # data layer, analytics, recommendations, AI service + prompts
│   ├── components/           # ui/, layout/, ai/, help/
│   ├── pages/                # Login, Dashboard, Analytics, Inventory, Orders, Menu, Reports…
│   └── styles/               # design tokens + per-page CSS
├── agent-core/               # FastAPI AI gateway (deployed to Railway)
│   ├── src/touchorders_core/ # api/ (routes + auth), llm/ (OpenAI gateway), settings, main
│   ├── tests/                # unit tests for the gateway
│   ├── railway.toml          # Railway build + start config
│   └── docs/deployment/      # secrets & deployment notes
├── firebase.json             # Firebase Hosting config (static SPA)
├── database.rules.json       # Realtime Database security rules
├── DEPLOYMENT.md             # end-to-end deployment guide
└── README.md
```

---

## Security

- **Firebase Authentication** — every user signs in with Firebase; the frontend never handles
  raw credentials beyond the sign-in form.
- **Firebase Security Rules** — [`database.rules.json`](database.rules.json) restricts each branch's
  data to its authorized user UIDs; the Realtime Database enforces access, not the client.
- **OpenAI key isolation** — the API key exists only in the Railway backend's environment variables.
  It is never in the frontend bundle, Firebase, or the repository.
- **Server-side token verification** — the FastAPI gateway verifies the caller's Firebase ID token
  (`firebase-admin`) on every AI request; anonymous requests are rejected with `401`.
- **Stateless gateway** — the backend persists nothing, so there is no operational data at rest
  outside Firebase to secure.

---

## Future Roadmap

- **Server-side prompt templates** — move prompt construction into the gateway to shrink client
  payloads and further harden the AI boundary.
- **True multi-agent synthesis** — have an Operations Manager role synthesize the Realtime Analyst
  and Business Analyst outputs within the existing single gateway call.
- **Deterministic-first recommendations everywhere** — surface computed recommendations instantly
  across all pages, with AI explanation on demand.
- **Provider portability** — abstract the gateway to support alternative models (e.g. Gemini) behind
  the same authenticated seam.
- **Multi-tenant access** — replace the pilot's UID allowlist with Firebase custom claims for
  scalable per-restaurant isolation.

---

## How We Used GPT-5.6, Claude, and Codex

This project was developed through a collaborative AI-assisted engineering workflow where each model
contributed according to its strengths.

### GPT-5.6 (Primary Development Partner)

GPT-5.6 was the primary AI model used throughout the project's implementation and production
development. It was heavily involved in the architectural redesign that transformed the project into
its current production-ready structure.

Major contributions include:

- Designing and refining the frontend → FastAPI → OpenAI gateway architecture.
- Refactoring the AI system from multiple disconnected implementations into a single authenticated AI service.
- Designing the production AI workflow that powers:
  - Executive Business Presentations
  - Executive Written Reports
  - Quick Insights
  - Live Operations Analysis
  - AI Analyst conversational interface
- Creating and refining the structured prompting system used by every AI mode.
- Improving the frontend architecture to separate deterministic analytics from AI-generated explanations.
- Designing the recommendation explanation workflow ("Why?") where AI explains deterministic business insights without inventing data.
- Planning and implementing conversation memory for the AI Analyst while minimizing token usage.
- Reviewing overall project architecture, identifying technical debt, and recommending production-ready improvements before submission.
- Assisting in preparing the project for deployment and hackathon submission.

GPT-5.6 was used continuously throughout development as the primary engineering assistant for
implementation decisions, production architecture, feature design, documentation, and technical
validation.

### Claude

Claude was used alongside GPT-5.6 throughout development, primarily for high-level software
architecture planning, long-form design discussions, code reviews, implementation audits, and system
analysis.

Major contributions include:

- Reviewing architectural decisions before implementation.
- Auditing completed features to verify they matched the intended design.
- Identifying missing capabilities and implementation gaps.
- Reviewing production readiness.
- Suggesting simplifications and cleaner architectural patterns.
- Assisting with technical documentation and repository organization.
- Providing detailed implementation reports and feature verification.

Rather than replacing GPT-5.6, Claude complemented it by acting as an architectural reviewer and
planning assistant. Both GPT-5.6 and Claude were used extensively throughout production development,
with each helping shape the final system from different perspectives.

### OpenAI Codex

Codex was primarily used as an implementation assistant for targeted engineering tasks rather than
high-level architecture.

Its primary responsibilities included:

- Fixing bugs.
- Resolving build errors.
- Refactoring existing components.
- Cleaning unused code.
- Simplifying implementations.
- Removing dead code.
- Updating documentation.
- Improving repository organization.
- Assisting with smaller production fixes and maintenance tasks.

Codex accelerated development by handling focused engineering work, allowing GPT-5.6 and Claude to
focus on larger architectural and system-level decisions.

### Overall Development Workflow

Our workflow combined the strengths of multiple AI models throughout the project lifecycle.

- **GPT-5.6** served as the primary engineering partner responsible for implementing major production features, designing the AI architecture, and guiding the overall technical direction.
- **Claude** acted as an architectural planning and review partner, helping validate designs, identify implementation gaps, and improve overall system quality.
- **Codex** was used for targeted engineering work such as debugging, refactoring, cleanup, and production fixes.

This collaborative workflow enabled us to rapidly iterate on a production-ready AI-powered restaurant
operations platform while maintaining a clean architecture, reusable AI services, and a scalable
codebase suitable for continued development beyond the hackathon.

---

## License

Released under the MIT License. See [`LICENSE`](LICENSE).
