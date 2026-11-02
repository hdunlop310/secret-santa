from datetime import date, timedelta

from sqlalchemy import select

from app.models import Exclusion, Group, Participant
from app.security import hash_token
from tests.conftest import bearer, group_payload, join, link_in, token_from


class TestCreateGroup:
    def test_creates_group_with_admin_as_participant(self, client, db, outbox):
        response = client.post("/groups", json=group_payload())
        assert response.status_code == 201
        body = response.json()
        assert body["admin_link"].startswith("http://localhost:5173/g/")
        assert body["invite_link"].startswith("http://localhost:5173/join/")
        assert "participant_link" not in body  # the admin link covers it

        group = db.scalar(select(Group))
        assert group.budget_min == 1500 and group.budget_max == 2500
        assert group.show_exclusions is False and group.draw_status == "not_drawn"
        (admin_p,) = group.participants
        assert admin_p.is_admin and admin_p.joined_at is not None

    def test_tokens_stored_only_as_hashes(self, client, db):
        body = client.post("/groups", json=group_payload()).json()
        admin_token = token_from(body["admin_link"])
        group = db.scalar(select(Group))
        assert group.admin_token_hash == hash_token(admin_token)
        # The organiser's participant row holds a hash of a token nobody was given.
        assert group.participants[0].token_hash not in (hash_token(admin_token), admin_token)
        assert len(group.participants[0].token_hash) == 64
        # The plain invite token is stored as-is, by design.
        assert group.invite_token == token_from(body["invite_link"])

    def test_admin_not_taking_part(self, client, db):
        body = client.post("/groups", json=group_payload(admin_participates=False)).json()
        assert db.scalar(select(Participant)) is None
        assert client.get("/me", headers=bearer(token_from(body["admin_link"]))).status_code == 404

    def test_emails_admin_one_link(self, client, outbox):
        body = client.post("/groups", json=group_payload()).json()
        (email,) = outbox.outbox
        assert email.to == "sam@example.com"
        assert body["admin_link"] in email.text and body["admin_link"] in email.html
        assert "/p/" not in email.text and "wish list" in email.text

    def test_email_is_lowercased_and_names_trimmed(self, client, db):
        client.post("/groups", json=group_payload(admin_email="Sam@Example.COM", name="  G  "))
        group = db.scalar(select(Group))
        assert group.admin_email == "sam@example.com" and group.name == "G"

    def test_validation(self, client):
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        for bad in (
            {"budget_min": 3000, "budget_max": 2000},
            {"budget_min": -1},
            {"gift_date": yesterday},
            {"admin_email": "not-an-email"},
            {"name": "   "},
            {"admin_name": ""},
            {"unexpected": "field"},
        ):
            assert client.post("/groups", json=group_payload(**bad)).status_code == 422, bad

    def test_rate_limited(self, client, monkeypatch):
        from app.config import get_settings

        monkeypatch.setattr(get_settings(), "rate_limit_group_create", 2)
        for _ in range(2):
            assert client.post("/groups", json=group_payload()).status_code == 201
        assert client.post("/groups", json=group_payload()).status_code == 429


class TestAdminGroup:
    def test_dashboard_data(self, client, outbox, make_group, db):
        g = make_group()
        join(client, outbox, g.invite, "Alex", "alex@example.com")
        response = client.get("/admin/group", headers=bearer(g.admin))
        assert response.status_code == 200
        body = response.json()
        assert body["name"] == "Family Secret Santa"
        assert body["invite_link"] == g.data["invite_link"]
        assert body["days_to_go"] == 49
        assert body["exclusion_pair_count"] == 0
        assert [(p["name"], p["status"], p["is_admin"]) for p in body["participants"]] == [
            ("Sam", "joined", True),
            ("Alex", "joined", False),
        ]

    def test_counts_mirrored_exclusions_as_one_pair(self, client, outbox, make_group, db):
        g = make_group()
        join(client, outbox, g.invite, "Alex", "alex@example.com")
        join(client, outbox, g.invite, "Jo", "jo@example.com")
        sam, alex, jo = db.scalars(select(Participant).order_by(Participant.id)).all()
        db.add_all(
            [
                Exclusion(group_id=g.id, giver_id=sam.id, giftee_id=alex.id),
                Exclusion(group_id=g.id, giver_id=alex.id, giftee_id=sam.id),
                Exclusion(group_id=g.id, giver_id=jo.id, giftee_id=sam.id),
            ]
        )
        db.commit()
        body = client.get("/admin/group", headers=bearer(g.admin)).json()
        assert body["exclusion_pair_count"] == 2

    def test_never_returns_emails_or_hashes(self, client, outbox, make_group, db):
        g = make_group()
        join(client, outbox, g.invite, "Alex", "alex@example.com")
        text = client.get("/admin/group", headers=bearer(g.admin)).text
        assert "@example.com" not in text
        for p in db.scalars(select(Participant)):
            assert p.token_hash not in text
        assert g.admin not in text

    def test_rejects_bad_tokens_uniformly(self, client, outbox, make_group):
        g = make_group()
        alex = join(client, outbox, g.invite, "Alex", "alex@example.com")
        responses = [
            client.get("/admin/group"),
            client.get("/admin/group", headers={"Authorization": "Basic abc"}),
            client.get("/admin/group", headers=bearer("nope")),
            client.get("/admin/group", headers=bearer(alex)),
            client.get("/admin/group", headers=bearer("x" * 500)),
        ]
        assert {r.status_code for r in responses} == {404}
        assert len({r.text for r in responses}) == 1


class TestGetAndPatchGroup:
    def test_members_can_read_their_group(self, client, outbox, make_group):
        g = make_group()
        alex = join(client, outbox, g.invite, "Alex", "alex@example.com")
        for token in (g.admin, alex):
            response = client.get(f"/groups/{g.id}", headers=bearer(token))
            assert response.status_code == 200
            assert response.json()["admin_name"] == "Sam"

    def test_token_must_match_group(self, client, make_group):
        g1, g2 = make_group(), make_group(name="Work")
        assert client.get(f"/groups/{g2.id}", headers=bearer(g1.admin)).status_code == 404
        assert (
            client.get(f"/groups/{g2.id}", headers=bearer(g1.admin_participant)).status_code == 404
        )
        assert (
            client.patch(f"/groups/{g2.id}", headers=bearer(g1.admin), json={}).status_code == 404
        )

    def test_admin_can_patch(self, client, make_group):
        g = make_group()
        response = client.patch(
            f"/groups/{g.id}",
            headers=bearer(g.admin),
            json={"name": "New name", "budget_max": 3000, "show_exclusions": True, "message": ""},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["name"] == "New name" and body["budget_max"] == 3000
        assert body["message"] is None
        admin = client.get("/admin/group", headers=bearer(g.admin)).json()
        assert admin["show_exclusions"] is True

    def test_patch_checks_budget_against_stored_values(self, client, make_group):
        g = make_group()
        response = client.patch(
            f"/groups/{g.id}", headers=bearer(g.admin), json={"budget_max": 100}
        )
        assert response.status_code == 422

    def test_participant_cannot_patch(self, client, outbox, make_group):
        g = make_group()
        alex = join(client, outbox, g.invite, "Alex", "alex@example.com")
        response = client.patch(f"/groups/{g.id}", headers=bearer(alex), json={"name": "Mine"})
        assert response.status_code == 404


class TestAddParticipant:
    def test_admin_adds_invited_person_who_gets_an_email(self, client, outbox, make_group):
        g = make_group()
        response = client.post(
            f"/groups/{g.id}/participants",
            headers=bearer(g.admin),
            json={"name": "Jo", "email": "jo@example.com"},
        )
        assert response.status_code == 201
        assert response.json()["status"] == "invited"
        email = outbox.outbox[-1]
        assert email.to == "jo@example.com" and "Sam added you" in email.text

        jo = token_from(link_in(email.text, "p"))
        statuses = lambda: {  # noqa: E731
            p["name"]: p["status"]
            for p in client.get("/admin/group", headers=bearer(g.admin)).json()["participants"]
        }
        assert statuses()["Jo"] == "invited"
        assert client.get("/me", headers=bearer(jo)).status_code == 200
        assert statuses()["Jo"] == "joined"

    def test_duplicate_email_conflicts(self, client, make_group):
        g = make_group()
        response = client.post(
            f"/groups/{g.id}/participants",
            headers=bearer(g.admin),
            json={"name": "Sam again", "email": "SAM@example.com"},
        )
        assert response.status_code == 409

    def test_participant_cannot_add(self, client, outbox, make_group):
        g = make_group()
        alex = join(client, outbox, g.invite, "Alex", "alex@example.com")
        response = client.post(
            f"/groups/{g.id}/participants",
            headers=bearer(alex),
            json={"name": "Jo", "email": "jo@example.com"},
        )
        assert response.status_code == 404


class TestRegenerateAdminLink:
    def test_old_link_stops_working_and_new_one_is_emailed(self, client, outbox, make_group):
        g = make_group()
        response = client.post(f"/groups/{g.id}/regenerate-admin-link", headers=bearer(g.admin))
        assert response.status_code == 204
        assert client.get("/admin/group", headers=bearer(g.admin)).status_code == 404
        new_admin = token_from(link_in(outbox.outbox[-1].text, "g"))
        assert client.get("/admin/group", headers=bearer(new_admin)).status_code == 200
