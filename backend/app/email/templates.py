"""Email content. Each email is a list of blocks: a paragraph, or a (label, url) button.

The plain-text and HTML versions are built from the same blocks so they never drift.
Every email to a participant or admin carries an unsubscribe footer that stops reminders
only. No email ever names someone's giftee.
"""

from html import escape

from app.email.senders import EmailMessage
from app.models import Group
from app.money import format_budget
from app.unsubscribe import UnsubscribeLinks

Block = str | tuple[str, str]


def _facts(group: Group) -> str:
    when = f"{group.gift_date.day} {group.gift_date:%b %Y}"
    return f"{when} · {format_budget(group.budget_min, group.budget_max)}"


def _text(blocks: list[Block], unsubscribe: UnsubscribeLinks | None) -> str:
    body = "\n\n".join(b if isinstance(b, str) else f"{b[0]}: {b[1]}" for b in blocks)
    if unsubscribe:
        body += f"\n\n--\nStop reminder emails: {unsubscribe.page}"
    return body


def _html(blocks: list[Block], unsubscribe: UnsubscribeLinks | None) -> str:
    parts = []
    for block in blocks:
        if isinstance(block, str):
            parts.append(f'<p style="margin:0 0 14px">{escape(block)}</p>')
        else:
            label, url = escape(block[0]), escape(block[1])
            parts.append(
                f'<p style="margin:18px 0 6px"><a href="{url}" style="display:inline-block;'
                "background:#1F4D3A;color:#FFFFFF;padding:12px 20px;border-radius:12px;"
                f'font-weight:700;text-decoration:none">{label}</a></p>'
                f'<p style="margin:0 0 18px;font-size:13px;color:#6B5D50">{url}</p>'
            )
    if unsubscribe:
        parts.append(
            '<p style="margin:24px 0 0;font-size:12px;color:#6B5D50">'
            f'<a href="{escape(unsubscribe.page)}" style="color:#6B5D50">'
            "Stop reminder emails</a></p>"
        )
    return (
        '<div style="font-family:Arial,sans-serif;font-size:15px;color:#2B2118;'
        f'background:#FBF6EE;padding:24px">{"".join(parts)}</div>'
    )


def _message(
    to: str, subject: str, blocks: list[Block], unsubscribe: UnsubscribeLinks | None
) -> EmailMessage:
    return EmailMessage(
        to=to,
        subject=subject,
        text=_text(blocks, unsubscribe),
        html=_html(blocks, unsubscribe),
        unsubscribe_url=unsubscribe.one_click if unsubscribe else None,
    )


# Links and confirmations


def admin_created(
    group: Group, link: str, participates: bool, unsubscribe: UnsubscribeLinks
) -> EmailMessage:
    blocks: list[Block] = [
        f'Your Secret Santa "{group.name}" is set up. {_facts(group)}.',
        "This is your link for running the group"
        + (", adding your wish list and seeing who you're buying for" if participates else "")
        + ". Keep it private: anyone with it can run the group.",
        ("Open your group", link),
    ]
    return _message(group.admin_email, f"Your link for {group.name}", blocks, unsubscribe)


def admin_link_regenerated(
    group: Group, admin_link: str, unsubscribe: UnsubscribeLinks
) -> EmailMessage:
    blocks: list[Block] = [
        f'A new link was created for "{group.name}". The old one no longer works.',
        ("Open your group", admin_link),
    ]
    return _message(group.admin_email, f"New link for {group.name}", blocks, unsubscribe)


def personal_link(
    group: Group, name: str, email: str, link: str, unsubscribe: UnsubscribeLinks
) -> EmailMessage:
    blocks: list[Block] = [
        f"Hi {name},",
        f'You\'re in "{group.name}". {_facts(group)}.',
        "Use this link to add your wish list and, after the draw, to see who you're buying "
        "for. Keep it private.",
        ("Open your wish list", link),
    ]
    return _message(email, f"Your link for {group.name}", blocks, unsubscribe)


def invited_by_admin(
    group: Group, name: str, email: str, link: str, unsubscribe: UnsubscribeLinks
) -> EmailMessage:
    blocks: list[Block] = [
        f"Hi {name},",
        f'{group.admin_name} added you to the Secret Santa "{group.name}". {_facts(group)}.',
    ]
    if group.message:
        blocks.append(f"From {group.admin_name}: {group.message}")
    blocks += [
        "Use this link to add your wish list and, after the draw, to see who you're buying "
        "for. Keep it private.",
        ("Open your wish list", link),
    ]
    return _message(email, f"You're invited to {group.name}", blocks, unsubscribe)


def lost_links(email: str, groups: list[tuple[str, str]]) -> EmailMessage:
    """Answer to the lost-link page: one button per group. The links expire in a day."""
    blocks: list[Block] = ["Here are your Secret Santa links. They work for 24 hours."]
    blocks += [(f"Open {name}", link) for name, link in groups]
    blocks.append("If you didn't ask for these, you can ignore this email.")
    return _message(email, "Your Secret Santa links", blocks, None)


def draw_done(
    group: Group,
    name: str,
    email: str,
    link: str,
    redraw: bool,
    unsubscribe: UnsubscribeLinks,
) -> EmailMessage:
    """Tells someone the draw happened. Never names their giftee: that stays behind the link."""
    if redraw:
        lead = (
            f'The names for "{group.name}" have been drawn again, '
            "so you may be buying for someone new."
        )
        subject = f"New draw for {group.name}"
    else:
        lead = f'The names for "{group.name}" have been drawn.'
        subject = f"Names drawn for {group.name}"
    blocks: list[Block] = [
        f"Hi {name},",
        f"{lead} {_facts(group)}.",
        ("See who you're buying for", link),
    ]
    return _message(email, subject, blocks, unsubscribe)


def participant_left(
    group: Group, name: str, redrawn: bool, link: str, unsubscribe: UnsubscribeLinks
) -> EmailMessage:
    """To the admin when someone removes themselves after the draw."""
    if redrawn:
        detail = "Names were drawn again for everyone else, and they've been emailed."
    else:
        detail = (
            "A new draw wasn't possible with the people and exclusions left, so the draw "
            "has been cleared. Fix the exclusions and run it again."
        )
    blocks: list[Block] = [
        f'{name} left "{group.name}" and their data was deleted.',
        detail,
        ("Open your group", link),
    ]
    return _message(group.admin_email, f"{name} left {group.name}", blocks, unsubscribe)


# Reminders (stopped by unsubscribing)


def invite_reminder(
    group: Group, name: str, email: str, link: str, unsubscribe: UnsubscribeLinks
) -> EmailMessage:
    blocks: list[Block] = [
        f"Hi {name},",
        f'{group.admin_name} added you to the Secret Santa "{group.name}". {_facts(group)}.',
        ("Add your wish list", link),
    ]
    return _message(email, f"Reminder: you're in {group.name}", blocks, unsubscribe)


def wishlist_nudge(
    group: Group, name: str, email: str, link: str, unsubscribe: UnsubscribeLinks
) -> EmailMessage:
    blocks: list[Block] = [
        f"Hi {name},",
        f'Your wish list for "{group.name}" is empty. Add a few ideas, or choose secret '
        "surprise, so your Secret Santa knows what to get you.",
        ("Add your wish list", link),
    ]
    return _message(email, f"Add your wish list for {group.name}", blocks, unsubscribe)


def gift_date_soon(
    group: Group,
    name: str,
    email: str,
    days: int,
    link: str,
    unsubscribe: UnsubscribeLinks,
) -> EmailMessage:
    when = "tomorrow" if days == 1 else f"in {days} days"
    blocks: list[Block] = [
        f"Hi {name},",
        f'The gift exchange for "{group.name}" is {when}. {_facts(group)}.',
        ("See your giftee's wish list", link),
    ]
    return _message(email, f"{group.name} is {when}", blocks, unsubscribe)


def draw_pending(group: Group, days: int, link: str, unsubscribe: UnsubscribeLinks) -> EmailMessage:
    when = "tomorrow" if days == 1 else f"in {days} days"
    blocks: list[Block] = [
        f'The gift exchange for "{group.name}" is {when}, and the names haven\'t been drawn.',
        ("Run the draw", link),
    ]
    return _message(group.admin_email, f"Run the draw for {group.name}", blocks, unsubscribe)


def wishlist_changed(
    group: Group, name: str, email: str, link: str, unsubscribe: UnsubscribeLinks
) -> EmailMessage:
    """To a giver. Says their giftee changed their list without naming who that is."""
    blocks: list[Block] = [
        f"Hi {name},",
        f'The person you\'re buying for in "{group.name}" has updated their wish list.',
        ("See what's new", link),
    ]
    return _message(email, f"Wish list updated in {group.name}", blocks, unsubscribe)
