# Deploying

| Part | Where | Staging | Production |
| --- | --- | --- | --- |
| Frontend | Cloudflare Pages | secretsanta-staging.dunlopdev.com | secretsanta.dunlopdev.com |
| API + Postgres | Render (`render.yaml`) | secretsanta-api-staging.dunlopdev.com | secretsanta-api.dunlopdev.com |
| Scheduled jobs | GitHub Actions (`.github/workflows/jobs.yml`), every 15 min | calls staging API | calls production API |
| Email | Resend, sending from `secretsanta.dunlopdev.com` | | |

Branches: `main` deploys to staging, `production` deploys to production. Promote by merging `main` into `production`.

Everything below needs your accounts. `render.yaml` currently sets up **staging only, on Render's free tier** (decided 2 Nov 2026): the API sleeps when idle and the free database is temporary. Production needs paid plans and is set up later (see the end of this file).

## 1. GitHub

1. Create a private repository and push this one to it, including a `production` branch (`git branch production && git push -u origin main production`).
2. CI (`ci.yml`) runs lint, unit tests and the Playwright test on every push.

## 2. Resend (email)

1. Create a Resend account.
2. Add the domain `secretsanta.dunlopdev.com`. Resend shows DNS records (SPF, DKIM, and a return-path MX). Add each one in Cloudflare DNS for dunlopdev.com, as **DNS only** (grey cloud). Wait for Resend to show the domain as verified.
3. Create an API key with sending access only. Keep it for step 3.

## 3. Render (API and database)

1. In Render: New, Blueprint, connect the GitHub repository. Render reads `render.yaml` and proposes one free database and one free web service.
2. Paste the Resend API key into `RESEND_API_KEY`. `SECRET_KEY` and `CRON_SECRET` are generated for you.
3. Apply. Each deploy installs with `uv`; each start runs `alembic upgrade head` and then the API. `/health` should return `{"status":"ok"}` on the `onrender.com` address (the first request after a sleep takes about a minute).
4. The custom domain is already listed in the blueprint. In Cloudflare DNS add `secretsanta-api-staging` as a CNAME to the service's `onrender.com` host, **DNS only**.

   DNS only matters: Render issues the certificate, and the API's rate limits assume exactly one proxy in front (`TRUSTED_PROXY_HOPS=1`). If you ever turn on the Cloudflare proxy for the API, set it to 2.

## 4. Cloudflare Pages (frontend)

Create two Pages projects from the same repository (Workers and Pages, Create, Pages, Connect to Git):

| Setting | `secretsanta-staging` | `secretsanta` |
| --- | --- | --- |
| Production branch | `main` | `production` |
| Root directory | `frontend` | `frontend` |
| Build command | `npm run build` | `npm run build` |
| Output directory | `dist` | `dist` |
| Env var `VITE_API_URL` | `https://secretsanta-api-staging.dunlopdev.com` | `https://secretsanta-api.dunlopdev.com` |
| Env var `NODE_VERSION` | `22` | `22` |
| Custom domain | `secretsanta-staging.dunlopdev.com` | `secretsanta.dunlopdev.com` |

`frontend/public/_redirects` sends every path to the app, and `frontend/public/_headers` sets the security headers (strict CSP, no referrer, no framing, noindex). If the API domains change, update `connect-src` in `_headers`.

## 5. Scheduled jobs

In the GitHub repository: Settings, Secrets and variables, Actions, and add:

| Secret | Value |
| --- | --- |
| `STAGING_API_URL` | `https://secretsanta-api-staging.dunlopdev.com` |
| `STAGING_CRON_SECRET` | `CRON_SECRET` from the staging service's environment on Render |
| `PRODUCTION_API_URL` | `https://secretsanta-api.dunlopdev.com` |
| `PRODUCTION_CRON_SECRET` | `CRON_SECRET` from the production service on Render |

Then run "Scheduled jobs" once by hand (Actions, Scheduled jobs, Run workflow). It should print something like `{"deleted_groups":0,"sent":{}}` for each environment. Until the secrets exist, the job skips that environment.

## 6. Check staging

1. Open https://secretsanta-staging.dunlopdev.com, create a group with your own email and a couple of other addresses you can read, join, add wish lists, set an exclusion, draw, and open each giftee page.
2. Check the emails arrive from `santa@secretsanta.dunlopdev.com`, the unsubscribe link works, and Gmail shows its own "Unsubscribe" button (that's the one-click header).
3. Run the scheduled jobs workflow and check nothing errors.

## Production checklist

- Add production to `render.yaml` on paid plans: a second database and web service copying staging's, on branch `production`, with the production URLs from the table at the top, and with migrations moved back to a `preDeployCommand`. Add the `secretsanta-api` CNAME and the `PRODUCTION_*` GitHub secrets.
- Self-host the Fraunces and DM Sans fonts (DESIGN.md asks for this before launch), then drop Google Fonts from `index.html` and the CSP.
- Rate limits live in memory, so run a single instance of the API. More than one needs the counters moved to Postgres or Redis.
- Postgres backups: check the plan's backup retention on Render.
