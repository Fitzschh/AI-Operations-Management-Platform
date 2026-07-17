# Railway secret design

This document defines the only supported way to provide credentials to a deployed
TouchOrders Agent Core. It preserves the architecture's single-LLM-gateway rule and ensures
no secret is stored in source control, `railway.toml`, client-side JavaScript, or application
logs.

## Trust boundary

```text
OpenAI project key ── Railway service variable ── llm.gateway (Stage 7) ── OpenAI API
                                                        │
React dashboard ───────────── REST / WebSocket ────────┘
                         never receives OPENAI_API_KEY
```

`OPENAI_API_KEY` is present only in the production **agent-core service** runtime
environment. It is not shared with the React dashboard service, background job services, or
the build process. `touchorders_core.settings` must never read it; Stage 7's
`touchorders_core.llm.gateway` is its sole application reader.

## OpenAI setup

1. Create separate OpenAI API Projects for `touchorders-development`,
   `touchorders-staging`, and `touchorders-production`.
2. In each production-like Project, create a dedicated service account for the deployed
   backend, for example `railway-touchorders-core-prod`. Do not use a founder's or developer's
   personal key in Railway.
3. Set the Project model allowlist and rate limits to only the models the approved agent
   definitions use. Configure OpenAI Project spend alerts, but retain the application's hard
   per-agent daily token budgets from Stage 7—the Project monthly budget is an alerting
   threshold, not a hard stop.
4. Copy the generated project-scoped service-account key exactly once into Railway's
   production service **Variables** UI as `OPENAI_API_KEY`. Never add it to the repository,
   `railway.toml`, a Docker build argument, or a client build variable such as `VITE_*`.

API-key endpoint restrictions are available for user-owned OpenAI keys. The current OpenAI UI
does not expose those controls for service-account keys, so containment for the Railway service
comes from the dedicated, project-scoped service account plus the Project's model/rate limits
and the application gateway's token budgets/circuit breaker.

## Railway variables

Create variables in Railway for the **agent-core service**, separately in each Railway
environment. The values below are names and safe examples only; secret values belong in the
Railway Variables UI or CLI, never in this repository.

| Variable | Classification | Production value / rule |
|---|---|---|
| `OPENAI_API_KEY` | secret | Dedicated OpenAI production Project service-account key. Service scope only. |
| `DATABASE_URL` | secret | Reference the Railway PostgreSQL service: `${{Postgres.DATABASE_URL}}`. |
| `AUTH_API_KEY_PEPPER` | secret | Fresh random value (at least 32 bytes); used only for keyed hashing in Stage 10. |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | secret | Full service-account JSON, scoped to the minimum Firebase paths; implemented in Stage 2. |
| `FIREBASE_DATABASE_URL` | sensitive configuration | RTDB URL; service scope only. |
| `AUTH_JWT_ISSUER` / `AUTH_JWT_AUDIENCE` | configuration | Firebase token validation values; do not put them in the frontend unless intentionally public. |
| `TOUCHORDERS_ENVIRONMENT` | configuration | `production` |
| `TOUCHORDERS_LOG_LEVEL` | configuration | `INFO` |
| `TOUCHORDERS_LOG_JSON` | configuration | `true` |

Keep variables service-scoped rather than project-shared unless a second trusted backend
service demonstrably needs the same value. Railway reference variables are appropriate for the
PostgreSQL connection string; do not copy it manually.

## Deployment configuration

`railway.toml` contains only non-secret build and liveness configuration. It starts the API on
Railway's injected `PORT` and checks `/health`. In this monorepo, set the Railway service root
directory to `agent-core`, or set the custom config path to `/agent-core/railway.toml`.

Before the first production deployment, set `TOUCHORDERS_ENVIRONMENT=production` and add the
variables above through Railway's Variables UI. Railway stages variable changes: review and
deploy them deliberately instead of treating a saved value as already active.

## Rotation and incident response

1. Create a replacement key in the same OpenAI Project.
2. Replace `OPENAI_API_KEY` in Railway, review the staged variable change, and deploy.
3. Verify `/health`, a controlled gateway smoke test after Stage 7, and the OpenAI Project
   usage dashboard.
4. Revoke the old OpenAI key only after the new deployment is healthy.
5. If a key reaches source control, browser code, logs, screenshots, or a chat transcript,
   revoke it immediately, rotate the Railway variable, and review deployment and OpenAI usage
   logs. Do not rely on a Git history rewrite as remediation.

## Authoritative references

- [OpenAI API key safety](https://platform.openai.com/docs/api-reference/backward-compatibility?lang=ruby)
- [OpenAI Projects, service accounts, limits, and budgets](https://help.openai.com/en/articles/9186755-managing-projects-in-the-api-platform)
- [Railway service variables](https://docs.railway.com/variables)
- [Railway configuration as code](https://docs.railway.com/config-as-code/reference)

## Non-negotiable implementation controls

- Only `touchorders_core.llm.gateway` may read `OPENAI_API_KEY` or import the OpenAI SDK.
- `llm.gateway` must create one SDK client at application composition and must never log
  headers, environment dumps, request objects, or raw exception payloads that could contain a
  credential.
- API routes, agents, tools, workflows, and the dashboard must receive only gateway results,
  never a provider key.
- Secret-bearing settings must be excluded from `/health`, OpenAPI, audit records, metrics,
  and structured logs.
- Production deployment requires a real PostgreSQL service. The local SQLite URL is only the
  single-node hackathon default and must not be backed by Railway's ephemeral filesystem.
