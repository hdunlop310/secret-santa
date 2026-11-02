# Deploying

| Part | Where | Staging | Production |
| --- | --- | --- | --- |
| Frontend | Vercel project (root `frontend`) | secretsanta-staging.dunlopdev.com | secretsanta.dunlopdev.com |
| API | Vercel project (root `backend`), serverless, London (`lhr1`) | secretsanta-api-staging.dunlopdev.com | secretsanta-api.dunlopdev.com |
| Database | Neon Postgres, London | project `secretsanta-staging` | project `secretsanta` |
| Migrations | GitHub Actions (`migrate.yml`) on push | from `main` | from `production` |
| Scheduled jobs | GitHub Actions (`jobs.yml`), every 15 min | calls staging API | calls production API |
| Email | Resend, sending from `secretsanta.dunlopdev.com` | | |
| DNS | Cloudflare (dunlopdev.com) | | |

Branches: `main` deploys staging, `production` deploys production. Promote by merging `main` into `production`.

Everything here runs on free plans (Vercel Hobby, Neon Free, Resend free, GitHub Actions on a private repo within its free minutes). Vercel Hobby is for personal, non-commercial use, which this is. Check each signup page yourself; free terms change.

Why four Vercel projects rather than two: staging and production each get a real "production" deployment, so no preview protection gets in the way and each has a single set of environment variables.

## 1. GitHub (done)

The private repository is https://github.com/hdunlop310/secret-santa with `main` and `production` branches. CI runs lint, unit tests and the Playwright test on every push.

## 2. Neon (database)

1. Create a Neon account and two projects, `secretsanta-staging` and `secretsanta`, both in **AWS Europe (London)**, Postgres 17.
2. For each project, copy two connection strings from the Connect dialog:
   - the **pooled** one (host contains `-pooler`), for Vercel
   - the **direct** one, for migrations

## 3. Resend (email)

1. Create a Resend account and add the domain `secretsanta.dunlopdev.com`.
2. Add the DNS records Resend shows in Cloudflare DNS, as **DNS only** (grey cloud), and wait until Resend says verified.
3. Create an API key with sending access.

## 4. GitHub environments

In the repository: Settings, Environments. Create `staging` and `production`, and in each add:

| Kind | Name | Value |
| --- | --- | --- |
| Secret | `DATABASE_URL` | that environment's Neon **direct** connection string |
| Secret | `CRON_SECRET` | a long random value, e.g. from `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| Variable | `API_URL` | `https://secretsanta-api-staging.dunlopdev.com` or `https://secretsanta-api.dunlopdev.com` |

Then run "Migrate database" by hand once for each branch (Actions, Migrate database, Run workflow, choose `main`, then `production`). It creates the tables.

## 5. Vercel

Create a Vercel account (Hobby) and import the GitHub repository four times:

| Project | Root directory | Production branch |
| --- | --- | --- |
| `secretsanta-api-staging` | `backend` | `main` |
| `secretsanta-api` | `backend` | `production` |
| `secretsanta-staging` | `frontend` | `main` |
| `secretsanta` | `frontend` | `production` |

Set the production branch under Settings, Git, after importing. Vercel reads `backend/pyproject.toml` (`[tool.vercel] entrypoint = "app.main:app"`) and `frontend/vercel.json` by itself.

API environment variables (Settings, Environment Variables, Production):

| Name | Staging | Production |
| --- | --- | --- |
| `ENVIRONMENT` | `production` | `production` |
| `DATABASE_URL` | staging Neon **pooled** string | production Neon **pooled** string |
| `DATABASE_POOLING` | `false` | `false` |
| `APP_BASE_URL` | `https://secretsanta-staging.dunlopdev.com` | `https://secretsanta.dunlopdev.com` |
| `API_BASE_URL` | `https://secretsanta-api-staging.dunlopdev.com` | `https://secretsanta-api.dunlopdev.com` |
| `CORS_ORIGINS` | same as `APP_BASE_URL` | same as `APP_BASE_URL` |
| `SECRET_KEY` | a new long random value | a different long random value |
| `CRON_SECRET` | the same value as the GitHub `staging` secret | the same value as the GitHub `production` secret |
| `EMAIL_BACKEND` | `resend` | `resend` |
| `EMAIL_FROM` | `Secret Santa <santa@secretsanta.dunlopdev.com>` | same |
| `RESEND_API_KEY` | your Resend key | your Resend key |
| `TRUSTED_PROXY_HOPS` | `1` | `1` |

Frontend environment variable: `VITE_API_URL` set to the matching API URL.

Redeploy each project after setting its variables. `https://<api>.vercel.app/health` should return `{"status":"ok"}`.

## 6. Domains

In each Vercel project, Settings, Domains, add its domain from the table at the top. Vercel shows a CNAME target. In Cloudflare DNS add each as a CNAME, **DNS only** (grey cloud), so Vercel can issue the certificate:

- `secretsanta-staging`, `secretsanta-api-staging`, `secretsanta`, `secretsanta-api`

If the API domains ever change, update `connect-src` in `frontend/vercel.json`.

## 7. Check staging

1. Run "Scheduled jobs" by hand (Actions). Each environment should print something like `{"deleted_groups":0,"sent":{}}`; one without its secrets is skipped.
2. Open https://secretsanta-staging.dunlopdev.com, create a group with your own email and a couple of other addresses you can read, join, add wish lists, set an exclusion, draw, and open each giftee page.
3. Check emails arrive from `santa@secretsanta.dunlopdev.com`, the unsubscribe link works, and Gmail shows its own "Unsubscribe" button.

## How the serverless setup differs

- Emails are sent before each response returns (draw emails in one Resend batch call), because nothing is guaranteed to run after a serverless response.
- Rate limits are counted in Postgres (`rate_limit_hits`, keys hashed), so all running copies of the API share them.
- `DATABASE_POOLING=false` opens a connection per request and turns off prepared statements, as Neon's pooler needs.

## Before launch

- Self-host the Fraunces and DM Sans fonts (DESIGN.md asks for this), then drop Google Fonts from `index.html` and the CSP.
- Neon's free plan has no point-in-time backups beyond a short window: check what it offers, or export now and then.
