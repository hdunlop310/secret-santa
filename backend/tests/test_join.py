from sqlalchemy import func, select, update

from app.models import Group, Participant
from app.security import hash_token, new_token
from tests.conftest import bearer, future, join, open_link_in, token_from


class TestInvitePreview:
    def test_shows_group_details(self, client, make_group):
        g = make_group()
        response = client.get(f"/join/{g.invite}")
        assert response.status_code == 200
        assert response.json() == {
            "group_name": "Family Secret Santa",
            "admin_name": "Sam",
            "gift_date": future(),
            "budget_min": 1500,
            "budget_max": 2500,
            "message": "One gift each.",
        }

    def test_unknown_invite(self, client):
        assert client.get("/join/nope").status_code == 404
        assert client.post("/join/nope", json={"name": "A", "email": "a@x.com"}).status_code == 404


class TestJoin:
    def test_join_creates_participant_and_emails_link(self, client, outbox, make_group, db):
        g = make_group()
        token = join(client, outbox, g.invite, "Alex", "Alex@Example.com")
        email = outbox.outbox[-1]
        assert email.to == "alex@example.com"
        alex = db.scalar(select(Participant).where(Participant.name == "Alex"))
        assert alex.token_hash == hash_token(token) and alex.joined_at is not None
        me = client.get("/me", headers=bearer(token)).json()
        assert me["name"] == "Alex" and me["group"]["name"] == "Family Secret Santa"

    def test_rejoin_only_emails_a_link(self, client, outbox, make_group, db):
        g = make_group()
        first = join(client, outbox, g.invite, "Alex", "alex@example.com")
        response = client.post(
            f"/join/{g.invite}", json={"name": "Someone else", "email": "alex@example.com"}
        )
        # Nobody is let in by typing a known email: the link goes to that inbox only.
        assert response.status_code == 202
        assert response.json() == {"status": "sent", "participant_link": None}
        email = outbox.outbox[-1]
        assert email.to == "alex@example.com" and "Hi Alex" in email.text
        opened = client.post(f"/links/open/{open_link_in(email.text)}")
        second = token_from(opened.json()["link"])
        assert first != second
        # Both links work: a re-send never breaks the older link.
        for token in (first, second):
            assert client.get("/me", headers=bearer(token)).json()["name"] == "Alex"
        assert db.scalar(select(func.count()).select_from(Participant)) == 2

    def test_participant_cap_of_50(self, client, outbox, make_group, db):
        g = make_group()  # Sam is participant 1
        db.add_all(
            Participant(
                group_id=g.id,
                name=f"P{i}",
                email=f"p{i}@example.com",
                token_hash=hash_token(new_token()),
            )
            for i in range(49)
        )
        db.commit()
        response = client.post(f"/join/{g.invite}", json={"name": "Late", "email": "late@x.com"})
        assert response.status_code == 409
        # Someone already in can still get their link re-sent.
        response = client.post(f"/join/{g.invite}", json={"name": "P1", "email": "p1@example.com"})
        assert response.status_code == 202

    def test_no_new_joins_after_draw(self, client, make_group, db):
        g = make_group()
        db.execute(update(Group).values(draw_status="drawn"))
        db.commit()
        response = client.post(f"/join/{g.invite}", json={"name": "Late", "email": "late@x.com"})
        assert response.status_code == 409

    def test_email_sends_are_rate_limited(self, client, make_group, monkeypatch):
        from app.config import get_settings

        g = make_group()
        monkeypatch.setattr(get_settings(), "rate_limit_email_send", 3)
        codes = [
            client.post(f"/join/{g.invite}", json={"name": "A", "email": "a@x.com"}).status_code
            for _ in range(4)
        ]
        # Group creation already used one send from this IP. The second join is a re-send.
        assert codes == [201, 202, 429, 429]

    def test_validation(self, client, make_group):
        g = make_group()
        for bad in ({"name": "", "email": "a@x.com"}, {"name": "A", "email": "nope"}, {}):
            assert client.post(f"/join/{g.invite}", json=bad).status_code == 422


class TestMe:
    def test_requires_participant_token(self, client, make_group):
        apart = make_group(admin_participates=False, admin_email="ann@example.com")
        assert client.get("/me", headers=bearer(apart.admin)).status_code == 404
        assert client.get("/me").status_code == 404
        g = make_group()
        assert client.get("/me", headers=bearer(g.admin)).json()["is_admin"] is True
