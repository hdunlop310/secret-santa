from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select, update

from app import jobs
from app.email.senders import EmailMessage
from app.models import Assignment, Group, Participant, Reminder
from app.unsubscribe import links, make_token, parse_token
from tests.conftest import bearer, join, link_in, token_from

NOON = datetime.now(UTC).replace(hour=12, minute=0, second=0, microsecond=0)


@pytest.fixture
def four(client, outbox, make_group):
    """Sam (admin, taking part), Alex, Priya and Jo, gift date 49 days away."""
    g = make_group()
    g.tokens = {"Sam": g.admin_participant}
    for name in ("Alex", "Priya", "Jo"):
        g.tokens[name] = join(client, outbox, g.invite, name, f"{name.lower()}@example.com")
    people = client.get("/admin/group", headers=bearer(g.admin)).json()["participants"]
    g.ids = {p["name"]: p["id"] for p in people}
    return g


def set_gift_date(db, g, days_from_today):
    db.execute(
        update(Group)
        .where(Group.id == g.id)
        .values(gift_date=NOON.date() + timedelta(days=days_from_today))
    )
    db.commit()


def age_everyone(db, g, days):
    then = NOON - timedelta(days=days)
    db.execute(
        update(Participant)
        .where(Participant.group_id == g.id)
        .values(created_at=then, joined_at=then)
    )
    db.commit()


def run(db, outbox, now=NOON):
    outbox.outbox.clear()
    db.expire_all()
    return jobs.run(db, outbox, now=now)


def sent_to(outbox, subject_part):
    return sorted(m.to for m in outbox.outbox if subject_part in m.subject)


class TestUnsubscribeTokens:
    def test_round_trip(self):
        assert parse_token(make_token("p", 42)) == ("p", 42)
        assert parse_token(make_token("a", 7)) == ("a", 7)

    @pytest.mark.parametrize(
        "token",
        ["", "p42", "p42.", "x42.0123456789abcdef0123456789abcdef", "p42." + "0" * 32],
    )
    def test_rejects_forgeries(self, token):
        assert parse_token(token) is None

    def test_signature_is_bound_to_who_and_kind(self):
        sig = make_token("p", 42).split(".")[1]
        assert parse_token(f"p43.{sig}") is None
        assert parse_token(f"a42.{sig}") is None

    def test_links(self):
        unsub = links("p", 5)
        assert unsub.page.startswith("http://localhost:5173/unsubscribe/p5.")
        assert unsub.one_click.startswith("http://localhost:8000/unsubscribe/p5.")


class TestUnsubscribeEndpoint:
    def test_participant(self, client, db, four):
        token = make_token("p", four.ids["Alex"])
        assert client.post(f"/unsubscribe/{token}").json() == {"status": "unsubscribed"}
        assert client.post(f"/unsubscribe/{token}").status_code == 200  # idempotent
        db.expire_all()
        assert db.get(Participant, four.ids["Alex"]).unsubscribed_at is not None
        # It stops reminders, nothing else: the personal link still works.
        assert client.get("/me", headers=bearer(four.tokens["Alex"])).status_code == 200

    def test_admin(self, client, db, four):
        client.post(f"/unsubscribe/{make_token('a', four.id)}")
        db.expire_all()
        assert db.get(Group, four.id).admin_unsubscribed_at is not None

    def test_bad_or_unknown(self, client):
        assert client.post("/unsubscribe/p1.nope").status_code == 404
        assert client.post(f"/unsubscribe/{make_token('p', 999999)}").status_code == 404


class TestEveryEmailCanUnsubscribe:
    def test_footer_and_one_click_headers(self, client, outbox, four):
        client.post(
            f"/groups/{four.id}/participants",
            headers=bearer(four.admin),
            json={"name": "Mia", "email": "mia@example.com"},
        )
        client.post(f"/groups/{four.id}/draw", headers=bearer(four.admin), json={})
        client.post(f"/groups/{four.id}/regenerate-admin-link", headers=bearer(four.admin))
        assert len(outbox.outbox) >= 10
        for message in outbox.outbox:
            assert "/unsubscribe/" in message.text, message.subject
            assert "Stop reminder emails" in message.html, message.subject
            headers = message.headers()
            assert headers["List-Unsubscribe"].startswith("<http://localhost:8000/unsubscribe/")
            assert headers["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"

    def test_no_headers_without_unsubscribe(self):
        assert EmailMessage("a@x.com", "s", "t", "h").headers() == {}


class TestDeletion:
    def test_deletes_groups_30_days_after_gift_date(self, client, db, outbox, four, make_group):
        kept = make_group(name="Kept", admin_email="k@example.com")
        set_gift_date(db, four, -31)
        set_gift_date(db, kept, -30)
        report = run(db, outbox)
        assert report.deleted_groups == 1
        db.expire_all()
        assert db.get(Group, four.id) is None and db.get(Group, kept.id) is not None
        assert (
            db.scalar(
                select(func.count()).select_from(Participant).where(Participant.group_id == four.id)
            )
            == 0
        )
        assert client.get("/me", headers=bearer(four.tokens["Alex"])).status_code == 404


class TestDailyReminders:
    def test_nothing_daily_before_nine(self, db, outbox, four):
        age_everyone(db, four, 10)
        report = run(db, outbox, now=NOON.replace(hour=8))
        assert report.sent == {}

    def test_wishlist_nudge_schedule(self, client, db, outbox, four):
        client.post("/me/items", headers=bearer(four.tokens["Alex"]), json={"title": "Socks"})
        client.put("/me", headers=bearer(four.tokens["Priya"]), json={"secret_surprise": True})
        age_everyone(db, four, 2)
        assert run(db, outbox).sent == {}  # too soon after joining

        age_everyone(db, four, 4)
        run(db, outbox)
        assert sent_to(outbox, "Add your wish list") == ["jo@example.com", "sam@example.com"]

        run(db, outbox, now=NOON + timedelta(days=1))
        assert sent_to(outbox, "Add your wish list") == []  # weekly, not daily

        run(db, outbox, now=NOON + timedelta(days=7))
        assert sent_to(outbox, "Add your wish list") == ["jo@example.com", "sam@example.com"]

    def test_invite_reminder_for_people_who_never_opened_their_link(self, client, db, outbox, four):
        client.post(
            f"/groups/{four.id}/participants",
            headers=bearer(four.admin),
            json={"name": "Mia", "email": "mia@example.com"},
        )
        db.execute(
            update(Participant)
            .where(Participant.email == "mia@example.com")
            .values(created_at=NOON - timedelta(days=4))
        )
        db.commit()
        run(db, outbox)
        assert sent_to(outbox, "Reminder: you're in") == ["mia@example.com"]
        run(db, outbox, now=NOON + timedelta(hours=1))
        assert sent_to(outbox, "Reminder: you're in") == []
        run(db, outbox, now=NOON + timedelta(days=3))
        run(db, outbox, now=NOON + timedelta(days=6))
        db.expire_all()
        mia = db.scalar(select(Participant).where(Participant.email == "mia@example.com"))
        invites = db.scalar(
            select(func.count()).where(Reminder.participant_id == mia.id, Reminder.type == "invite")
        )
        assert invites == 2  # capped

    def test_gift_date_reminders_once_each(self, client, db, outbox, four):
        for token in four.tokens.values():
            client.put("/me", headers=bearer(token), json={"secret_surprise": True})
        client.post(f"/groups/{four.id}/draw", headers=bearer(four.admin), json={})
        set_gift_date(db, four, 7)
        run(db, outbox)
        assert len(sent_to(outbox, "is in 7 days")) == 4
        run(db, outbox, now=NOON + timedelta(hours=3))
        assert sent_to(outbox, "is in 7 days") == []
        set_gift_date(db, four, 1)
        run(db, outbox)
        assert len(sent_to(outbox, "is tomorrow")) == 4

    def test_draw_pending_goes_to_the_admin(self, db, outbox, four):
        set_gift_date(db, four, 3)
        run(db, outbox)
        assert sent_to(outbox, "Run the draw") == ["sam@example.com"]

    def test_unsubscribed_people_get_no_reminders(self, client, db, outbox, four):
        for name in four.tokens:
            client.post(f"/unsubscribe/{make_token('p', four.ids[name])}")
        client.post(f"/unsubscribe/{make_token('a', four.id)}")
        age_everyone(db, four, 10)
        set_gift_date(db, four, 7)
        assert run(db, outbox).sent == {}

    def test_reminders_never_name_a_giftee(self, client, db, outbox, four):
        client.post(f"/groups/{four.id}/draw", headers=bearer(four.admin), json={})
        set_gift_date(db, four, 7)
        age_everyone(db, four, 10)
        run(db, outbox)
        assert outbox.outbox
        names = set(four.ids)
        for message in outbox.outbox:
            recipient = message.to.split("@")[0].capitalize()
            for other in names - {recipient, "Sam"}:  # Sam is named as the host
                assert other not in message.text, (message.subject, other)


class TestWishlistChanged:
    def giver_of(self, db, g, name):
        db.expire_all()
        giver_id = db.scalar(
            select(Assignment.giver_id).where(
                Assignment.group_id == g.id, Assignment.giftee_id == g.ids[name]
            )
        )
        return db.get(Participant, giver_id)

    def test_not_before_the_draw(self, client, db, four):
        client.post("/me/items", headers=bearer(four.tokens["Alex"]), json={"title": "Socks"})
        assert db.scalar(select(func.count()).select_from(Reminder)) == 0

    def test_burst_of_edits_sends_one_email_to_the_giver(self, client, db, outbox, four):
        client.post(f"/groups/{four.id}/draw", headers=bearer(four.admin), json={})
        alex = bearer(four.tokens["Alex"])
        item = client.post("/me/items", headers=alex, json={"title": "Socks"}).json()
        client.patch(f"/me/items/{item['id']}", headers=alex, json={"price": 1500})
        client.post("/me/items", headers=alex, json={"title": "Book"})
        db.expire_all()
        assert db.scalar(select(func.count()).where(Reminder.type == "wishlist_changed")) == 1

        now = datetime.now(UTC)
        run(db, outbox, now=now)  # still inside the short delay
        assert sent_to(outbox, "Wish list updated") == []

        run(db, outbox, now=now + timedelta(minutes=20))
        giver = self.giver_of(db, four, "Alex")
        assert sent_to(outbox, "Wish list updated") == [giver.email]
        (message,) = [m for m in outbox.outbox if "Wish list updated" in m.subject]
        assert "Alex" not in message.text

        # The next edit waits until an hour after that email.
        client.post("/me/items", headers=alex, json={"title": "Scarf"})
        run(db, outbox, now=now + timedelta(minutes=40))
        assert sent_to(outbox, "Wish list updated") == []
        run(db, outbox, now=now + timedelta(minutes=81))
        assert sent_to(outbox, "Wish list updated") == [giver.email]

    def test_giver_who_unsubscribed_is_skipped(self, client, db, outbox, four):
        client.post(f"/groups/{four.id}/draw", headers=bearer(four.admin), json={})
        giver = self.giver_of(db, four, "Alex")
        client.post(f"/unsubscribe/{make_token('p', giver.id)}")
        client.post("/me/items", headers=bearer(four.tokens["Alex"]), json={"title": "Socks"})
        run(db, outbox, now=datetime.now(UTC) + timedelta(minutes=20))
        assert sent_to(outbox, "Wish list updated") == []


class TestLeaving:
    def test_before_the_draw(self, client, db, four):
        client.post("/me/items", headers=bearer(four.tokens["Jo"]), json={"title": "Socks"})
        assert client.delete("/me", headers=bearer(four.tokens["Jo"])).status_code == 204
        assert client.get("/me", headers=bearer(four.tokens["Jo"])).status_code == 404
        db.expire_all()
        assert db.get(Participant, four.ids["Jo"]) is None

    def test_after_the_draw_redraws_and_tells_everyone(self, client, db, outbox, four):
        client.post(f"/groups/{four.id}/draw", headers=bearer(four.admin), json={})
        outbox.outbox.clear()
        assert client.delete("/me", headers=bearer(four.tokens["Jo"])).status_code == 204
        db.expire_all()
        pairs = db.execute(
            select(Assignment.giver_id, Assignment.giftee_id).where(Assignment.group_id == four.id)
        ).all()
        assert {g for g, _ in pairs} == {four.ids[n] for n in ("Sam", "Alex", "Priya")}
        assert len(sent_to(outbox, "New draw")) == 3
        (admin_mail,) = [m for m in outbox.outbox if "left" in m.subject]
        assert admin_mail.to == "sam@example.com" and "drawn again" in admin_mail.text

    def test_after_the_draw_when_no_redraw_is_possible(self, client, db, outbox, make_group):
        g = make_group()
        alex = join(client, outbox, g.invite, "Alex", "alex@example.com")
        join(client, outbox, g.invite, "Priya", "priya@example.com")
        client.post(f"/groups/{g.id}/draw", headers=bearer(g.admin), json={})
        outbox.outbox.clear()
        assert client.delete("/me", headers=bearer(alex)).status_code == 204
        db.expire_all()
        group = db.get(Group, g.id)
        assert group.draw_status == "not_drawn" and group.drawn_at is None
        assert db.scalar(select(func.count()).where(Assignment.group_id == g.id)) == 0
        (admin_mail,) = outbox.outbox
        assert "cleared" in admin_mail.text

    def test_admin_token_cannot_use_delete_me(self, client, four):
        assert client.delete("/me", headers=bearer(four.admin)).status_code == 404

    def test_admin_deletes_the_group(self, client, db, four):
        assert client.delete("/admin/group", headers=bearer(four.admin)).status_code == 204
        db.expire_all()
        assert db.get(Group, four.id) is None
        assert client.get("/admin/group", headers=bearer(four.admin)).status_code == 404
        assert client.get("/me", headers=bearer(four.tokens["Alex"])).status_code == 404

    def test_participant_cannot_delete_the_group(self, client, four):
        assert client.delete("/admin/group", headers=bearer(four.tokens["Sam"])).status_code == 404


class TestCronEndpoint:
    def test_disabled_without_a_secret(self, client):
        assert client.post("/internal/jobs/run", headers=bearer("anything")).status_code == 404

    def test_requires_the_secret(self, client, monkeypatch):
        from app.config import get_settings

        monkeypatch.setattr(get_settings(), "cron_secret", "s3cret-value")
        assert client.post("/internal/jobs/run", headers=bearer("wrong")).status_code == 404
        response = client.post("/internal/jobs/run", headers=bearer("s3cret-value"))
        assert response.status_code == 200
        assert set(response.json()) == {"deleted_groups", "sent"}


def test_added_person_link_is_in_their_email(client, outbox, four):
    """Sanity check that the invite email still carries a working personal link."""
    client.post(
        f"/groups/{four.id}/participants",
        headers=bearer(four.admin),
        json={"name": "Mia", "email": "mia@example.com"},
    )
    token = token_from(link_in(outbox.outbox[-1].text, "p"))
    assert client.get("/me", headers=bearer(token)).json()["name"] == "Mia"


def test_settings_refuse_dev_secrets_in_production():
    from pydantic import ValidationError

    from app.config import Settings

    with pytest.raises(ValidationError):
        Settings(environment="production", email_backend="resend")
    with pytest.raises(ValidationError):
        Settings(environment="production", secret_key="x" * 40, email_backend="console")
    Settings(environment="production", secret_key="x" * 40, email_backend="resend")
