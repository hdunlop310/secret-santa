"""Email content. Each email is a list of blocks: a paragraph, or a (label, url) button.

The plain-text and HTML versions are built from the same blocks so they never drift.
"""

from html import escape

from app.email.senders import EmailMessage
from app.models import Group
from app.money import format_budget

Block = str | tuple[str, str]


def _facts(group: Group) -> str:
    when = f"{group.gift_date.day} {group.gift_date:%b %Y}"
    return f"{when} · {format_budget(group.budget_min, group.budget_max)}"


def _text(blocks: list[Block]) -> str:
    return "\n\n".join(b if isinstance(b, str) else f"{b[0]}: {b[1]}" for b in blocks)


def _html(blocks: list[Block]) -> str:
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
    return (
        '<div style="font-family:Arial,sans-serif;font-size:15px;color:#2B2118;'
        f'background:#FBF6EE;padding:24px">{"".join(parts)}</div>'
    )


def _message(to: str, subject: str, blocks: list[Block]) -> EmailMessage:
    return EmailMessage(to=to, subject=subject, text=_text(blocks), html=_html(blocks))


def admin_created(group: Group, admin_link: str, personal_link: str | None) -> EmailMessage:
    blocks: list[Block] = [
        f'Your Secret Santa "{group.name}" is set up. {_facts(group)}.',
        "This is your admin link. Keep it private: anyone with it can run the group.",
        ("Open your group", admin_link),
    ]
    if personal_link:
        blocks += [
            "This is your personal link, for your own wish list and giftee.",
            ("Open your wish list", personal_link),
        ]
    return _message(group.admin_email, f"Your admin link for {group.name}", blocks)


def admin_link_regenerated(group: Group, admin_link: str) -> EmailMessage:
    blocks: list[Block] = [
        f'A new admin link was created for "{group.name}". The old one no longer works.',
        ("Open your group", admin_link),
    ]
    return _message(group.admin_email, f"New admin link for {group.name}", blocks)


def personal_link(group: Group, name: str, email: str, link: str) -> EmailMessage:
    blocks: list[Block] = [
        f"Hi {name},",
        f'Here is your personal link for "{group.name}". {_facts(group)}.',
        "Use it to add your wish list and, after the draw, to see who you're buying for. "
        "Keep it private.",
        ("Open your wish list", link),
    ]
    return _message(email, f"Your link for {group.name}", blocks)


def invited_by_admin(group: Group, name: str, email: str, link: str) -> EmailMessage:
    blocks: list[Block] = [
        f"Hi {name},",
        f'{group.admin_name} added you to the Secret Santa "{group.name}". {_facts(group)}.',
    ]
    if group.message:
        blocks.append(f"From {group.admin_name}: {group.message}")
    blocks += [
        "Use this personal link to add your wish list and, after the draw, to see who "
        "you're buying for. Keep it private.",
        ("Open your wish list", link),
    ]
    return _message(email, f"You're invited to {group.name}", blocks)
