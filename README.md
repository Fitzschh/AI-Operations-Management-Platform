# E-Menu Portal V2 — Powered by Touch

The next-generation AI-Assisted Restaurant Operations & Analytics platform, built as a
**drop-in replacement** for the Version 1 pilot (`AI-automated-restaurant-operations`).
Both versions run against the **same Firebase project and the same Realtime Database
structure** so pilot testers can compare them side by side during Week 2.

## What's new vs Version 1

| Area | Version 2 |
|---|---|
| Design | Café-first design system inspired by the V1 login: espresso/caramel/cream palette, Fraunces menu-style serif + Inter + JetBrains Mono, warm glass sidebar/topbar, rounded cards, soft shadows, dark ("espresso bar") & light ("daylight café") themes, micro-animations, loading skeletons |
| Dashboard | Executive command center: animated KPI counters, sparklines, vs-yesterday / vs-last-week deltas, deterministic AI commentary, Business Health Score with explainable breakdown, alerts, top/slow products, tomorrow's forecast, ranked smart recommendations (problem → evidence → impact → confidence) |
| Analytics | BI workspace with Today / Yesterday / 7d / 30d / 12-months / custom period switching, interactive SVG charts (area, bar, donut, hour heat-strip), category revenue mix, statistical overview |
| AI | Unified **AI Business Analyst** drawer (work chat, shift briefing, revenue-leak detector, what-if simulator) + **Executive Presentation**: a full-screen, autoplaying, scene-by-scene board-meeting briefing narrated by the AI |
| Inventory | Health score, predicted shortages ("~2 days left at current pace"), urgency sorting, smart filters, animated stock indicators, threshold editing, adjustment history |
| Orders | Live order cards with search, detail modal, trash bin; **Order Ledger** with include/exclude analytics corrections (fully mobile-friendly) |
| Reports | Print-ready executive report (Print → Save as PDF) with charts, tables, forecast outlook and optional AI commentary |
| Mobile | Mobile-first: bottom navigation, safe-area insets, bottom-sheet modals, no hidden actions |
| Performance | One shared realtime data provider (V1 opened duplicate Firebase listeners per page), route-level code splitting, dependency-free SVG charts |

## Compatibility guarantees

- **Same database, zero migrations.** All reads/writes go through the V1 data layer,
  copied verbatim into `src/lib` (`analyticsApi`, `inventoryApi`, `menuApi`, …).
- **Same background processors.** Order → analytics ledger and order → inventory
  consumption run identically (`useAnalyticsProcessor`, `useInventoryProcessor`).
- **Same auth model.** Firebase email/password + `src/config/authConfig.js` branch map.
- **Same Firebase config strategy.** Real config values in `.env` (copied from V1),
  loaded via Vite env vars exactly like V1 — Spark-plan friendly, no server runtime.
- **Same AI integration.** Client-side OpenAI calls with V1's prompt builders and JSON
  modes (`realtime`, `deep`, `executive`, `briefing`, `leak`, `simulation`, `opschat`).

## Run

```bash
npm install
npm run dev        # local development
npm run build      # production build to dist/
firebase deploy --only hosting   # deploys dist/ (see firebase.json)
```

> Deploying both versions: V1 and V2 share one Firebase project. Deploy them to two
> hosting sites (e.g. `firebase hosting:sites:create ops-manager-v2`, add a target in
> `firebase.json`) or deploy V2 to a separate channel:
> `firebase hosting:channel:deploy v2`.

## Structure

```
src/
  config/authConfig.js      # branch/role map (V1-identical)
  context/                  # Auth, Theme, BranchData (shared live streams)
  hooks/                    # V1 processors + useIsMobile
  lib/                      # V1 data layer (verbatim) + recommendations.js (V2)
  components/
    ui/                     # AnimatedNumber, Sparkline, charts, Modal, ScoreRing…
    layout/                 # AppShell (sidebar/topbar/bottom-nav), SettingsModal
    ai/                     # AIAnalystDrawer, ExecutivePresentation
  pages/                    # Login, Dashboard, Analytics, Inventory, Orders,
                            # Menu, Reports, HistoryPage (ledger), AdminHome
  styles/                   # tokens.css (design system), base.css, per-page css
```

## Honesty rules (carried over from V1, enforced in UI)

- Forecasts are always labeled **AI forecast** with a confidence percentage.
- Metrics without underlying data say so ("No comparison data", "Needs more history")
  instead of showing invented numbers.
- The profit figure on the dashboard is explicitly labeled an **estimate** with its
  assumed margin.
