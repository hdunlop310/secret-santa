from datetime import date, timedelta

import pytest
from sqlalchemy import func, select, update

from app.models import Assignment, Group, Participant, WishlistItem
from tests.conftest import bearer, join, link_in, token_from

NAMES = ("Alex", "Priya", "Jo", "Mia")


@pytest.fixture
def five(client, outbox, make_group):
    """Sam (admin, taking part), Alex, Priya, Jo and Mia."""
    g = make_group()
    g.tokens = {"Sam": g.admin_participant}
    for name in NAMES:
        g.tokens[name] = join(client, outbox, g.invite, name, f"{name.lower()}@example.com")
    people = client.get("/admin/group", headers=bearer(g.admin)).json()["participants"]
    g.ids = {p["name"]: p["id"] for p in people}
    g.names = {v: k for k, v in g.ids.items()}
    return g


def run_draw(client, g, confirm=False):
    return client.post(
        f"/groups/{g.id}/draw", headers=bearer(g.admin), json={"confirm_redraw": confirm}
    )


def assignments(db, g):
    db.expire_all()
    rows = db.execute(
        select(Assignment.giver_id, Assignment.giftee_id, Assignment.draw_round).where(
            Assignment.group_id == g.id
        )
    ).all()
    return {giver: giftee for giver, giftee, _ in rows}, {r for *_, r in rows}


def giftee_of(client, token):
    return client.get("/me/giftee", headers=bearer(token)).json()


class TestDraw:
    def test_draw_stores_one_round_and_returns_no_pairs(self, client, db, outbox, five):
        outbox.outbox.clear()
        response = run_draw(client, five)
        assert response.status_code == 200
        body = response.json()
        assert set(body) == {"draw_status", "drawn_at", "participant_count"}
        assert body["draw_status"] == "drawn" and body["participant_count"] == 5

        pairs, rounds = assignments(db, five)
        assert rounds == {1}
        assert set(pairs) == set(five.ids.values()) == set(pairs.values())
        assert all(g != t for g, t in pairs.items())

        # Everyone is emailed, and no email names the recipient's giftee.
        assert sorted(m.to for m in outbox.outbox) == sorted(
            f"{n.lower()}@example.com" for n in ("Sam", *NAMES)
        )
        by_email = {f"{n.lower()}@example.com": n for n in five.ids}
        for message in outbox.outbox:
            giver = five.ids[by_email[message.to]]
            giftee_name = five.names[pairs[giver]]
            assert giftee_name not in message.text and giftee_name not in message.html
            assert "drawn" in message.text

    def test_dashboard_reflects_the_draw(self, client, five):
        run_draw(client, five)
        admin = client.get("/admin/group", headers=bearer(five.admin)).json()
        assert admin["draw_status"] == "drawn" and admin["drawn_at"]

    def test_needs_three_people(self, client, outbox, make_group):
        g = make_group()
        join(client, outbox, g.invite, "Alex", "alex@example.com")
        response = run_draw(client, g)
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "too_few"

    def test_impossible_exclusions_name_the_bottleneck(self, client, db, five):
        sam = five.ids["Sam"]
        blocked = [x for x in five.ids.values() if x != sam]
        client.put(
            f"/groups/{five.id}/exclusions",
            headers=bearer(five.admin),
            json={"pairs": [{"giver_id": sam, "giftee_id": t} for t in blocked]},
        )
        response = run_draw(client, five)
        assert response.status_code == 409
        detail = response.json()["detail"]
        assert detail["code"] == "no_valid_draw"
        assert detail["bottleneck"] == {"side": "give", "people": [sam], "options": []}
        assert assignments(db, five)[0] == {}

    def test_respects_exclusions(self, client, db, five):
        pairs = [("Sam", "Alex"), ("Alex", "Sam"), ("Priya", "Jo")]
        client.put(
            f"/groups/{five.id}/exclusions",
            headers=bearer(five.admin),
            json={"pairs": [{"giver_id": five.ids[a], "giftee_id": five.ids[b]} for a, b in pairs]},
        )
        for _ in range(5):
            run_draw(client, five, confirm=True)
            drawn, _ = assignments(db, five)
            for a, b in pairs:
                assert drawn[five.ids[a]] != five.ids[b]

    def test_admin_only(self, client, five):
        for token in (five.tokens["Alex"], five.tokens["Priya"]):
            response = client.post(
                f"/groups/{five.id}/draw", headers=bearer(token), json={"confirm_redraw": True}
            )
            assert response.status_code == 404

    def test_not_after_the_gift_date(self, client, db, five):
        db.execute(update(Group).values(gift_date=date.today() - timedelta(days=1)))
        db.commit()
        response = run_draw(client, five)
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "gift_date_passed"

    def test_new_people_cannot_join_by_invite_after_the_draw(self, client, five):
        run_draw(client, five)
        response = client.post(
            f"/join/{five.invite}", json={"name": "Late", "email": "late@example.com"}
        )
        assert response.status_code == 409
        # Someone already in can still get a fresh link.
        response = client.post(
            f"/join/{five.invite}", json={"name": "Alex", "email": "alex@example.com"}
        )
        assert response.status_code == 202


class TestRedraw:
    def test_redraw_needs_confirmation(self, client, five):
        run_draw(client, five)
        response = run_draw(client, five)
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "confirm_redraw"

    def test_confirmed_redraw_replaces_the_round_and_emails_everyone(
        self, client, db, outbox, five
    ):
        run_draw(client, five)
        outbox.outbox.clear()
        assert run_draw(client, five, confirm=True).status_code == 200
        pairs, rounds = assignments(db, five)
        assert rounds == {2} and len(pairs) == 5
        assert len(outbox.outbox) == 5
        assert all("drawn again" in m.text for m in outbox.outbox)

    def test_redraws_are_rate_limited(self, client, five, monkeypatch):
        from app.config import get_settings

        monkeypatch.setattr(get_settings(), "rate_limit_draw", 2)
        assert run_draw(client, five).status_code == 200
        assert run_draw(client, five, confirm=True).status_code == 200
        response = run_draw(client, five, confirm=True)
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "too_many_draws"


class TestRemove:
    def url(self, g, name, confirm=False):
        return f"/groups/{g.id}/participants/{g.ids[name]}?confirm_redraw={str(confirm).lower()}"

    def test_before_the_draw_removes_person_and_data(self, client, db, five):
        client.post("/me/items", headers=bearer(five.tokens["Jo"]), json={"title": "Socks"})
        response = client.delete(self.url(five, "Jo"), headers=bearer(five.admin))
        assert response.status_code == 204
        assert client.get("/me", headers=bearer(five.tokens["Jo"])).status_code == 404
        assert db.scalar(select(func.count()).select_from(WishlistItem)) == 0
        names = [
            p["name"]
            for p in client.get("/admin/group", headers=bearer(five.admin)).json()["participants"]
        ]
        assert "Jo" not in names

    def test_after_the_draw_needs_confirmation_then_redraws(self, client, db, outbox, five):
        run_draw(client, five)
        response = client.delete(self.url(five, "Jo"), headers=bearer(five.admin))
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "confirm_redraw"
        assert db.get(Participant, five.ids["Jo"]) is not None

        outbox.outbox.clear()
        response = client.delete(self.url(five, "Jo", True), headers=bearer(five.admin))
        assert response.status_code == 204
        pairs, rounds = assignments(db, five)
        assert rounds == {2}
        assert set(pairs) == {five.ids[n] for n in ("Sam", "Alex", "Priya", "Mia")}
        assert sorted(m.to for m in outbox.outbox) == sorted(
            f"{n}@example.com" for n in ("sam", "alex", "priya", "mia")
        )

    def test_removal_that_makes_a_draw_impossible_changes_nothing(
        self, client, db, outbox, make_group
    ):
        g = make_group()
        alex = join(client, outbox, g.invite, "Alex", "alex@example.com")
        join(client, outbox, g.invite, "Priya", "priya@example.com")
        run_draw(client, g)
        alex_id = client.get("/me", headers=bearer(alex)).json()["id"]
        response = client.delete(
            f"/groups/{g.id}/participants/{alex_id}?confirm_redraw=true",
            headers=bearer(g.admin),
        )
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "too_few"
        assert db.get(Participant, alex_id) is not None
        assert len(assignments(db, g)[0]) == 3

    def test_admin_only_and_same_group(self, client, five, make_group):
        other = make_group(name="Other", admin_email="o@example.com")
        assert (
            client.delete(self.url(five, "Jo"), headers=bearer(five.tokens["Alex"])).status_code
            == 404
        )
        assert client.delete(self.url(five, "Jo"), headers=bearer(other.admin)).status_code == 404
        response = client.delete(
            f"/groups/{other.id}/participants/{five.ids['Jo']}", headers=bearer(other.admin)
        )
        assert response.status_code == 404


class TestAddAfterDraw:
    def test_needs_confirmation_then_redraws_and_invites(self, client, db, outbox, five):
        run_draw(client, five)
        body = {"name": "Kai", "email": "kai@example.com"}
        url = f"/groups/{five.id}/participants"
        response = client.post(url, headers=bearer(five.admin), json=body)
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "confirm_redraw"

        outbox.outbox.clear()
        response = client.post(
            url, headers=bearer(five.admin), json={**body, "confirm_redraw": True}
        )
        assert response.status_code == 201
        pairs, rounds = assignments(db, five)
        assert rounds == {2} and len(pairs) == 6
        kai_mail = [m for m in outbox.outbox if m.to == "kai@example.com"]
        assert len(kai_mail) == 1 and "added you" in kai_mail[0].text
        kai = token_from(link_in(kai_mail[0].text, "p"))
        assert giftee_of(client, kai)["drawn"] is True
        assert len([m for m in outbox.outbox if "drawn again" in m.text]) == 5

    def test_duplicate_email_after_draw_changes_nothing(self, client, db, five):
        run_draw(client, five)
        response = client.post(
            f"/groups/{five.id}/participants",
            headers=bearer(five.admin),
            json={"name": "Alex 2", "email": "alex@example.com", "confirm_redraw": True},
        )
        assert response.status_code == 409
        assert assignments(db, five)[1] == {1}


class TestGiftee:
    def test_before_the_draw(self, client, five):
        assert giftee_of(client, five.tokens["Alex"]) == {"drawn": False, "giftee": None}

    def test_each_person_sees_only_their_own_giftee(self, client, db, five):
        for name, token in five.tokens.items():
            client.post("/me/items", headers=bearer(token), json={"title": f"{name}'s wish"})
        run_draw(client, five)
        pairs, _ = assignments(db, five)
        for name, token in five.tokens.items():
            body = giftee_of(client, token)
            expected = five.names[pairs[five.ids[name]]]
            assert body["drawn"] is True
            assert body["giftee"]["name"] == expected
            assert [i["title"] for i in body["giftee"]["items"]] == [f"{expected}'s wish"]
            assert "id" not in body["giftee"]

    def test_secret_surprise_hides_items(self, client, db, five):
        run_draw(client, five)
        pairs, _ = assignments(db, five)
        alex_giftee = five.names[pairs[five.ids["Alex"]]]
        token = five.tokens[alex_giftee]
        client.post("/me/items", headers=bearer(token), json={"title": "Hidden"})
        client.put("/me", headers=bearer(token), json={"secret_surprise": True})
        body = giftee_of(client, five.tokens["Alex"])["giftee"]
        assert body["secret_surprise"] is True and body["items"] == []

    def test_updated_since_draw(self, client, db, five):
        run_draw(client, five)
        pairs, _ = assignments(db, five)
        giftee_name = five.names[pairs[five.ids["Alex"]]]
        before = giftee_of(client, five.tokens["Alex"])["giftee"]
        assert before["updated_since_draw"] is False
        client.post("/me/items", headers=bearer(five.tokens[giftee_name]), json={"title": "New"})
        after = giftee_of(client, five.tokens["Alex"])["giftee"]
        assert after["updated_since_draw"] is True and after["updated_at"]

    def test_admin_link_shows_only_the_organisers_own_giftee(self, client, five, db):
        run_draw(client, five)
        sam = db.scalar(select(Participant).where(Participant.is_admin))
        giftee_id = db.scalar(select(Assignment.giftee_id).where(Assignment.giver_id == sam.id))
        body = client.get("/me/giftee", headers=bearer(five.admin)).json()
        assert body["giftee"]["name"] == db.get(Participant, giftee_id).name

    def test_admin_not_taking_part_has_no_giftee(self, client, outbox, make_group):
        g = make_group(admin_participates=False)
        for name in ("Alex", "Priya", "Jo"):
            join(client, outbox, g.invite, name, f"{name.lower()}@example.com")
        client.post(f"/groups/{g.id}/draw", headers=bearer(g.admin), json={})
        assert client.get("/me/giftee", headers=bearer(g.admin)).status_code == 404
