# Build plan

Written before milestone 1. Source of truth stays `SPEC.md` (behaviour) and `DESIGN.md` (visuals).

## Repo layout

```
backend/
  pyproject.toml            uv project (fastapi, pydantic, sqlalchemy, alembic, psycopg, httpx, pytest, ruff)
  alembic.ini, migrations/
  app/
    main.py                 FastAPI app, router wiring
    config.py               settings from environment
    db.py                   engine, session dependency
    models.py               SQLAlchemy 2.0 models (the six tables)
    schemas.py              Pydantic v2 request and response models
    security.py             token generation, SHA-256 hashing, constant-time compare, auth dependencies
    ratelimit.py            small limiter for group creation and email sends
    money.py                pence parsing and formatting
    email/                  EmailSender interface; console, smtp, resend implementations; templates
    routers/                groups.py, join.py, me.py (later: wishlist, exclusions, draw)
    matching/               milestone 3
  tests/
frontend/
  src/
    styles/tokens.css       DESIGN.md tokens as CSS variables
    components/             HeaderBand, Button, Input, Chip, Avatar, ParticipantRow
    pages/                  CreateGroup, Dashboard, Join, CheckEmail, ErrorPage (later: WishList, Exclusions, Giftee)
    api.ts                  fetch wrapper (Bearer token), TanStack Query hooks
docs/                       SPEC, DESIGN, PLAN, design-reference
docker-compose.yml          postgres, mailpit
Makefile                    dev, test, lint, migrate
.env.example
.github/workflows/ci.yml    ruff + pytest, eslint/tsc + vitest
```

## Route map (frontend)

| Route | Screen |
| --- | --- |
| `/`, `/new` | Create group |
| `/g/:adminToken` | Admin dashboard |
| `/g/:adminToken/exclusions` | Exclusions grid (M3) |
| `/join/:inviteToken` | Join |
| `/join/:inviteToken/check-email` | Check your email (after join) |
| `/p/:participantToken` | Wish list (M2) |
| `/p/:participantToken/giftee` | Giftee reveal (M4) |
| `*` | Invalid or expired link |

The token is read from the URL path and sent as `Authorization: Bearer <token>`. It is never put in a query string.

## API (milestone 1 shapes)

Errors are `{"detail": "<message>"}` with a stable `code` field: `{"code": "...", "detail": "..."}`. Auth failures always return the same 404 body so a bad token does not reveal whether a group exists.

`POST /groups` (no auth, rate limited)
```
request  { name, gift_date, budget_min, budget_max, message?, admin_name, admin_email, admin_participates }
         budget_* in pence; the form takes pounds and converts
response { group_id, admin_token, admin_link, invite_link, participant_link? }   // tokens shown once
```

`GET /admin/group` (admin token) resolves the token to a group; the dashboard needs this because its URL has no group id.
```
response { id, name, gift_date, budget_min, budget_max, message, admin_name, invite_link, show_exclusions,
           draw_status, days_to_go, exclusion_pair_count,
           participants: [{ id, name, status: "invited" | "joined" | "wish_list_in", is_admin }] }
```
Never contains emails of other people beyond what the admin entered, tokens, or assignments.

`GET /groups/{id}` (admin or participant token, id must match) returns the group fields a participant may see: name, gift_date, budget, message, admin_name.
`PATCH /groups/{id}` (admin) edits name, date, budget, message, show_exclusions.

`GET /join/{invite_token}` (no auth) returns `{ group_name, admin_name, gift_date, budget_min, budget_max, message }` for the join screen. The spec only lists POST, but the screen needs this.

`POST /join/{invite_token}` (no auth, rate limited): `{ name, email }` returns `204`. Always the same response whether or not the email already exists; an existing participant is sent a fresh link instead of an error. Fails with 409 once the group has 50 people or the draw has run (after the draw, joining needs an admin-confirmed redraw, handled in M4).

`POST /join/{invite_token}/resend` is not needed: re-joining with the same email is the re-send path ("re-send link" on the check-email screen calls `POST /join/{invite_token}` again).

`GET /me` (participant token) returns `{ id, name, group: {...}, secret_surprise, items: [] }`. Wish-list writes arrive in M2.

`POST /groups/{id}/participants` (admin): `{ name, email }`, adds an "invited" person and emails their link (spec F2). Backend only in M1; no UI because the reference screens have none.

`POST /groups/{id}/regenerate-admin-link` (admin): rotates the admin token, emails the new link to the admin email.

## API (milestone 2 shapes)

All participant token. Items are `{ id, title, url, price, image_url }`, price in pence, returned in `sort_order`.

- `PUT /me` `{ name?, secret_surprise? }` returns the same shape as `GET /me`.
- `POST /me/items` `{ title, url?, price?, image_url? }` returns 201 with the item. Max 50 items. `url` must be http(s) with no credentials; `image_url` also can't be a private IP literal or localhost, since it loads in the giver's browser.
- `PATCH /me/items/{id}` with any of those fields. Changing `url` without sending `image_url` clears the old preview image. The title can't be cleared.
- `DELETE /me/items/{id}` returns 204.
- `PUT /me/items/order` `{ ids: [...] }` must list every own item exactly once.
- `POST /link-preview` `{ url }` returns `{ title, image_url }`, always 200, nulls on any failure or when rate limited (60 per participant per hour). Rules in `backend/app/linkpreview.py`: public addresses only (checked for every resolved address and after each redirect), connect to the checked IP with SNI for the real host (no DNS rebinding), default ports only, 3 redirects, 512 KB, 5 s overall.

Reordering uses up/down buttons on each card: the reference screen has no reorder control, and buttons work with a keyboard and screen reader where drag and drop would not.

## API (milestone 3 shapes)

- `GET /groups/{id}/exclusions` (admin, or a participant when `show_exclusions` is on) returns `{ show_exclusions, participants: [{ id, name }], pairs: [{ giver_id, giftee_id }] }`. One row per blocked direction.
- `PUT /groups/{id}/exclusions` (admin) `{ pairs, show_exclusions? }` replaces all pairs. Saving an impossible set is allowed; the screen warns and the draw refuses.
- `POST /groups/{id}/exclusions/check` (admin) `{ pairs }` checks unsaved pairs with the real matching code: `{ possible, reason: null | "too_few" | "stuck", bottleneck: { side: "give" | "receive", people, options } }`. The screen calls it 250 ms after each change.

Matching lives in `backend/app/matching.py`: feasibility and the bottleneck come from bipartite matching and Hall's theorem (exact, instant); the draw tries a single Hamiltonian cycle, then a cover with no two-person swaps, then any matching, all from `random.SystemRandom`.

The grid is keyboard navigable: one cell is in the tab order and the arrow keys move between cells, skipping the diagonal. With many people it scrolls sideways inside its card while the giver names stay pinned.

## Migrations

1. `0001_initial`: groups, participants, exclusions, assignments, wishlist_items, reminders as in the spec, plus the fields below. Created in M1 so later milestones only add columns.
2. Later milestones add migrations only if needed (for example `unsubscribed_at`, `last_wishlist_email_at`).

## Spec gaps and things I think are wrong or missing

1. **Hashed tokens cannot be re-sent.** Participant and admin tokens are stored as hashes, so "re-send link" must issue a new token and invalidate the old one. I will do that. Consequence: a re-send kills a link someone already has open.
2. **No `group_id` in the token URLs.** `/g/:adminToken` has no id, so I added `GET /admin/group`. `/me` already covers participants.
3. **Invite token** is `token_urlsafe(16)`, not the short `k3x9` in the reference. It is stored plain text as the spec says; anyone with it can join, which is the intent.
4. **Participant statuses.** The dashboard shows Invited, Joined and Wish list in. "Invited" only exists if the admin can add people by email (F2), so I added `POST /groups/{id}/participants` without a UI. Say if you want an "add by email" form on the dashboard.
5. **Admin as participant** has two tokens (admin and participant). The admin link is shown once and emailed; the personal link is emailed and shown once after creation.
6. **Lock date for redraw (F10)** is not defined anywhere. Proposal: no separate date; redraw is allowed any time before the gift date, and always with a confirmation and a notification email. Needs your decision before M4.
7. **Reminder cadence (F11)** says the admin sets it but no screen has the control. Proposal: fixed defaults for v1 (wish-list nudge 3 days after joining then weekly, gift-date reminder 7 days and 1 day before), no UI.
8. **Wish-list-changed emails** use the `reminders` table with a `type` and a `send_at`, batched to one per hour per giver. Needs `last_sent_at` logic in M5.
9. **Rate limiting** has no stack library. I will use a small in-process limiter keyed by IP and by email. That is correct for a single instance; if deployed on more than one, it needs Postgres or Redis. Flagging now so hosting is chosen with that in mind.
10. **Assignment encryption** ("consider encrypting") is optional. I will skip it in v1: assignments are readable by the database owner either way, and the requirement that matters (no API leaks) is tested.
11. **Currency input.** The form takes pounds with optional pence (`18`, `18.50`) and converts to pence server-side; the API only deals in integers.
12. **Date and countdown.** `days_to_go` is computed server-side in UTC from `gift_date`.
13. **Deletion after gift date** needs a stored `gift_date`; changing the date moves the deletion date. Fine, noted.
14. **Draw rounds.** Older rounds are kept "for audit" but the secrecy rule says nothing may reveal who has whom. I will keep only the active round's rows and delete superseded ones, which also satisfies data minimisation.

## Milestone 1 build order

1. Scaffold repo, `docker-compose.yml`, `Makefile`, `.env.example`, CI workflow.
2. Backend: config, db, models, migration, security helpers (tests), money helpers (tests), rate limiter (tests).
3. Backend: email interface, console and SMTP senders, templates (invite link, personal link, admin link), `POST /groups`, `GET /admin/group`, `GET /groups/{id}`, `GET`/`POST /join/{invite_token}`, `GET /me`, add-participant, regenerate-admin-link. Tests for each, including: token hashing, wrong-group tokens, participant cap, duplicate email, rate limits, no emails or tokens in responses.
4. Frontend: tokens.css, layout and shared components, Create group, Dashboard, Join, Check your email, error page. Vitest for form validation and dashboard status rendering.
5. Manual run-through against the "done when" for M1 using Mailpit.
