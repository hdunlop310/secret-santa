# Claude Code build prompt

Run from the repo root: `claude "Read PROMPT.md and follow it"`, or paste everything below the line.

---

You are building **Secret Santa**, a free, ad-free web app where a group runs a Secret Santa without accounts. The admin creates a group with a budget, shares an invite link, sets which pairs can't be matched (for example couples), and runs the draw. Each participant keeps a wish list that only their Secret Santa can see.

## Read first

1. `CLAUDE.md`: standing rules. Follow them throughout.
2. `docs/SPEC.md`: source of truth for behaviour, data model, API and security.
3. `docs/DESIGN.md` and `docs/design-reference/*.html`: source of truth for visuals. Open `docs/design-reference/index.html` in a browser at about 390px wide and match what you see. Reuse the tokens from `DESIGN.md` as CSS variables.

If the spec and the design disagree, the design wins on layout and copy, the spec wins on behaviour.

## Stack

- `backend/`: Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic, PostgreSQL, pytest, ruff. Use `uv` for dependencies.
- `frontend/`: React, TypeScript, Vite, React Router, TanStack Query, plain CSS with CSS variables (no UI kit), Vitest and Testing Library.
- `docker-compose.yml` with Postgres and Mailpit for local email.
- Email behind an `EmailSender` interface: console or SMTP (Mailpit) in development, Resend in production, chosen by environment variable.
- A `Makefile` with `dev`, `test`, `lint` and `migrate` targets, and a `.env.example`.

## How to work

1. Start by writing a short plan to `docs/PLAN.md`: repo layout, route map, API request and response shapes, migrations, and anything in the spec you think is wrong or missing. Then begin milestone 1.
2. Build one milestone at a time (below). At the end of each: tests pass, lint is clean, the app runs, work is committed with conventional commit messages. Then give me a short summary and stop until I say to continue.
3. Write tests alongside the code, not afterwards.
4. Ask me before choosing hosting, buying a domain, creating accounts with paid services, or adding dependencies that aren't in the stack above.

## Non-negotiables

- **Secrecy.** No endpoint, log, error, email or test fixture reveals the full list of who has whom. A giver's request returns only their own giftee. Admin endpoints never return assignments. Add an integration test that walks every route as the admin and as other participants and asserts nothing leaks.
- **Tokens.** Admin and participant tokens are 128-bit or longer, stored as SHA-256 hashes, compared in constant time, never logged. Sent as `Authorization: Bearer <token>`; the frontend reads them from the URL path. The invite token is stored in plain text.
- **Money.** Pence in the database, GBP only, formatted as `£18` or `£18.50`.
- **Link previews.** Fetching a pasted URL must block private, loopback and link-local addresses (including after redirects), cap redirects, response size and time, and never block saving an item if it fails.
- **Draw.** Uses a secure random source, follows the algorithm and edge cases in the spec, and is covered by unit tests: impossible exclusion sets, 3-person groups, one-way exclusions, large groups of 50 with many exclusions, and no two-person swaps in groups of 4 or more when avoidable.
- **UI.** Mobile first, tap targets at least 44px, contrast at least 4.5:1, real buttons and labels, `aria-label` on icon-only buttons, no emoji, and no extra helper text, reassurance lines or marketing copy beyond what the reference screens show. Respect `prefers-reduced-motion`.

## Things the spec leaves implicit

These were added during design and are already in `docs/SPEC.md`; implement them:

- The create-group screen collects the admin's name and email and an "I'm taking part too" checkbox. If checked, the admin also becomes a participant with their own personal link. The admin link is shown once after creation and emailed to the admin.
- `groups.show_exclusions` (default false) controls whether participants can see the exclusions. The admin always sees them.
- `participants.secret_surprise` lets someone skip their wish list; their giver sees "[Name] wants to be surprised" instead of a list.
- After the draw, wish lists stay editable. Changes email the giver, batched so a burst of edits sends at most one email an hour.
- The giftee and wish-list screens flag any item priced above the group maximum with an "over budget" tag, for both the owner and the giver.

## Milestones

### 1. Foundations, groups, invites, identity

- Repo scaffolding, Docker, Makefile, CI workflow (lint and tests on push), design tokens and a shared layout (header band, buttons, inputs, chips).
- Create group (screen: `create-group.html`), dashboard shell (`dashboard.html`) with invite link and people list, join via invite link (`join.html`) with the magic-link email, re-send link.
- Rate limiting on group creation and email sends, participant cap of 50.
- Done when: I can create a group, copy the invite link, join as two other people in another browser, see all three on the dashboard with correct statuses, and receive the emails in Mailpit.

### 2. Wish lists

- Wish list screen (`wish-list.html`): add, edit, reorder, delete items; secret surprise; over-budget tag.
- Link preview endpoint with the safety rules above.
- Done when: items save with and without links, previews appear when available, a blocked or failing URL still saves, and tests cover the safety rules.

### 3. Exclusions and matching

- Exclusions grid (`exclusions.html`): tap cells, mirrored by default, one-way toggle, "Group these people", show-to-participants toggle, live "valid draw is still possible" check using the real matching code.
- Matching module with the algorithm from the spec and thorough unit tests.
- Done when: the grid saves and reloads exactly, the check turns negative and names the bottleneck people when exclusions make a draw impossible, and the matching tests pass.

### 4. Draw, reveal, redraw

- Run the draw from the dashboard, store assignments once, email everyone that the draw is done.
- Giftee screen (`giftee-reveal.html`) including the secret surprise variant and the "updated 2 hours ago" indicator.
- Redraw rules from the spec; adding or removing someone after the draw forces a confirmed redraw.
- Done when: every participant sees only their own giftee, the admin sees no assignments anywhere, and the leak-check integration test passes.

### 5. Reminders, cleanup, polish, deploy

- Daily reminder job (invite, wish list nudge, gift date approaching) with unsubscribe links that stop reminders only; the wish-list-changed email from the rules above.
- Auto-deletion of personal data 30 days after the gift date; let anyone remove themselves and their data.
- The undesigned states in `DESIGN.md` (check your email, draw complete, no valid draw, errors, loading, empty), in the same style.
- Optional motion from `DESIGN.md` if time allows.
- Deployment config for the hosting options in the spec on a subdomain of dunlopdev.com. Ask me to choose before you set anything up.
- Done when: the whole flow works end to end on a staging deployment and a Playwright test covers create, join, wish list, exclusions, draw and reveal.

## Out of scope

Accounts or passwords, payments or affiliate links, anonymous chat, native apps, multiple currencies, multiple languages, venue details.
