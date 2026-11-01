# Secret Santa: project instructions

Free, ad-free Secret Santa web app. No user accounts: people act through private link tokens. Read `docs/SPEC.md` for behaviour and `docs/DESIGN.md` for visuals before changing anything substantial.

## Layout

- `backend/`: FastAPI app, SQLAlchemy models, Alembic migrations, pytest tests
- `frontend/`: React + TypeScript + Vite single-page app
- `docs/`: spec, design, static design reference (do not edit the reference HTML to "fix" the app; change the app)

## Hard rules

- Secrecy is the product. No endpoint, log line, error message, email or test fixture may reveal the full list of who has whom. A giver's request returns only their own giftee. Admin endpoints never return assignments.
- Tokens (admin, participant) are `secrets.token_urlsafe(16)` or longer, stored as SHA-256 hashes, compared in constant time, and never logged. The invite token is stored in plain text because the admin needs to see it.
- Money is stored in minor units (pence), GBP only.
- Fetching a URL for link previews must block private, loopback and link-local addresses, follow few redirects, and enforce size and time limits.
- Personal data is deleted 30 days after the gift date.
- Use a secure random source (`secrets` / `random.SystemRandom`) for the draw.

## UI rules

- Mobile first: design at 390px wide, tap targets at least 44px, text contrast at least 4.5:1.
- Use the tokens in `docs/DESIGN.md` as CSS variables. No UI kit, no emoji, no gradients.
- Keep copy minimal. Do not add explanatory helper text, reassurance lines or marketing microcopy that the designed screens don't have.
- Real `<button>`, `<a>`, `<label>` + `<input>`. Icon-only buttons need `aria-label`.
- Respect `prefers-reduced-motion` for any animation.

## Workflow

- Work in small commits using conventional commit messages.
- Every behaviour change in the draw, exclusions, tokens or visibility needs a test.
- Run lint and tests before saying a milestone is done.
- Ask before choosing hosting, buying domains or adding paid services.

## Commands

Filled in as the project is built (a `Makefile` with `dev`, `test`, `lint`, `migrate` is part of milestone 1).
