# Design: Cosy Cabin

Warm, traditional and calm. A deep pine header over a cream page, berry red for the main action, small gold touches. The static reference screens are in `docs/design-reference/` (open `index.html`); they are the visual source of truth. This file lists the tokens and rules so they can be reused as CSS variables.

## Tokens

### Colour

| Token | Value | Use |
| --- | --- | --- |
| `--cream` | `#FBF6EE` | Page background |
| `--surface` | `#FFFFFF` | Cards, inputs |
| `--surface-muted` | `#F3EBDD` | Link box, "Joined" chip |
| `--surface-dashed` | `#F5EEDF` | "Add an item" card |
| `--border` | `#E7DCCB` | Card borders, dividers (`#F0E7D8` for row dividers) |
| `--border-strong` | `#8C7B68` | Input borders, dashed borders |
| `--ink` | `#2B2118` | Body text |
| `--muted` | `#6B5D50` | Secondary text |
| `--pine` | `#1F4D3A` | Header, primary buttons, links |
| `--pine-tint` | `#DDE9E1` | Avatar and "Wish list in" chip background |
| `--berry` | `#B3262E` | Main call to action, blocked cells, destructive text |
| `--berry-tint` | `#F6DADB` | Alternate avatar background (text `#8F1D25`) |
| `--gold` | `#F0DDA8` | Chips on pine, countdown pill, step numbers |
| `--on-pine-muted` | `#E9E2D2` | Secondary text on pine |
| `--warn-bg` / `--warn-border` / `--warn-text` | `#FFF1CC` / `#B7791F` / `#5C3B00` | Over-budget tag |
| `--cell-disabled` | `#EDE4D3` | Diagonal cell in the exclusions grid |

White text on pine and on berry passes AA. Do not use gold for text on cream.

### Type

- Headings and the giftee name: Fraunces, weight 700. H1 28 to 34px; H2 17 to 20px; reveal name 60px.
- Everything else: DM Sans, 400, 500 and 700. Body 15px, labels 13px bold, captions and chips 12px bold.
- Load both from Google Fonts (self-host before launch).

### Shape and spacing

- Cards 16px radius, inputs and secondary buttons 12px, primary buttons 14px, chips 10 to 14px, avatars 32px circles.
- Header band: pine with a bottom radius of 28px (32px on the join and reveal screens), 20px side padding, a few faint white dots as "snow".
- Page side padding 16px (20px on forms). Gaps of 10 to 12px between cards.
- Tap targets at least 44px high. Buttons 44 to 52px.

## Components

- **Header band:** pine, snowflake line icon plus "Secret Santa" in gold at the top, then the page title in Fraunces white, then one line of facts in `--on-pine-muted`.
- **Primary button:** pine fill, white text (form submits, copy). **Main action button:** berry fill, white text (run the draw, join, save exclusions). **Secondary:** transparent with a 1.5px pine border.
- **Inputs:** white, 1.5px `--border-strong`, 12px radius, 44px high, visible label above, placeholder text only as an example.
- **Chips:** pine-tint for "Wish list in", muted cream for "Joined", dashed outline for "Invited", gold for date and budget, warn colours for "over budget".
- **Participant row:** 32px initial avatar (alternating pine-tint and berry-tint), name, status chip right-aligned, divider above each row.
- **Gift-tag card:** white card with a small punched hole at the top left and corner radii `6px 18px 18px 18px`; title and price on the first line, then link, then status or actions.
- **Exclusions grid:** givers down the side, giftees across the top. Blocked cell: berry fill with a white "×". Allowed: white with a dashed border. Diagonal: disabled, `--cell-disabled`. Each cell is a real button with an `aria-label` like "Sam to Alex, blocked".

## Screens and routes

| Reference file | Screen | Suggested route |
| --- | --- | --- |
| `create-group.html` | Create a Secret Santa (admin) | `/` and `/new` |
| `dashboard.html` | Group dashboard (admin): countdown, invite link, people, exclusions, run the draw | `/g/:adminToken` |
| `exclusions.html` | Who can't be matched? (admin) | `/g/:adminToken/exclusions` |
| `join.html` | You're invited | `/join/:inviteToken` |
| `wish-list.html` | Your wish list (participant) | `/p/:participantToken` |
| `giftee-reveal.html` | You're Secret Santa for... (participant, after the draw) | `/p/:participantToken/giftee` |

## States that are not designed yet

Extend the same style for these, keeping copy minimal: "check your email" after joining, draw complete (admin, with no assignments shown), no valid draw possible (name the bottleneck people), loading, empty wish list, error pages for an invalid or expired link, and the "secret surprise" version of the giftee screen ("[Name] wants to be surprised").

## Motion ideas (optional, after the core flow works)

Unwrap animation when the giftee is revealed, a few falling snow dots on the join and reveal screens, and a short confetti burst when the draw completes. All must switch off under `prefers-reduced-motion`.
