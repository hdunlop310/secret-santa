# Secret Santa

A free, ad-free web app for running a Secret Santa with friends or family. The organiser sets a budget and exclusions (for example, couples never get paired), everyone joins from an invite link with no account, the app draws names, and each person's wish list is visible only to their Secret Santa.

Status: spec and design are done, code is not started. This repo is the handover package for building it with Claude Code.

## What's here

| Path | What it is |
| --- | --- |
| `docs/SPEC.md` | Product spec: flows, requirements, matching algorithm, data model, API, security |
| `docs/DESIGN.md` | The "Cosy Cabin" visual design: tokens, components, screen-to-route map |
| `docs/design-reference/` | Static HTML for the six designed screens. Open `index.html` in a browser at about 390px wide |
| `PROMPT.md` | The prompt to paste into Claude Code to build the app, milestone by milestone |
| `CLAUDE.md` | Standing project instructions Claude Code reads automatically |

## Stack

Python (FastAPI, SQLAlchemy, Alembic) and PostgreSQL on the backend. React, TypeScript and Vite on the frontend. Transactional email through a provider (Resend, Postmark or SES).

## Starting the build

From the repo root:

```
claude "Read PROMPT.md and follow it"
```

Claude Code will write a plan, then build one milestone at a time and stop after each for review.

## Spec additions

While designing the screens, a few fields were needed that the original spec didn't list. They are folded into `docs/SPEC.md`: admin name and email on the group, a group setting for whether participants can see exclusions, and a "secret surprise" flag on participants.
