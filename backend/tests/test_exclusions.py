import pytest

from tests.conftest import bearer, join


@pytest.fixture
def five(client, outbox, make_group):
    """Sam (admin, taking part), Alex, Priya, Jo and Mia."""
    g = make_group()
    tokens = {"Sam": g.admin_participant}
    for name in ("Alex", "Priya", "Jo", "Mia"):
        tokens[name] = join(client, outbox, g.invite, name, f"{name.lower()}@example.com")
    people = client.get("/admin/group", headers=bearer(g.admin)).json()["participants"]
    g.ids = {p["name"]: p["id"] for p in people}
    g.tokens = tokens
    return g


def pairs(g, *names):
    return [{"giver_id": g.ids[a], "giftee_id": g.ids[b]} for a, b in names]


def put(client, g, body):
    return client.put(f"/groups/{g.id}/exclusions", headers=bearer(g.admin), json=body)


def check(client, g, body):
    return client.post(f"/groups/{g.id}/exclusions/check", headers=bearer(g.admin), json=body)


class TestSaveAndLoad:
    def test_saves_and_reloads_exactly(self, client, five):
        body = {
            "pairs": pairs(five, ("Sam", "Alex"), ("Alex", "Sam"), ("Priya", "Jo")),
            "show_exclusions": True,
        }
        response = put(client, five, body)
        assert response.status_code == 200
        loaded = client.get(f"/groups/{five.id}/exclusions", headers=bearer(five.admin)).json()
        assert loaded["show_exclusions"] is True
        got = {(p["giver_id"], p["giftee_id"]) for p in loaded["pairs"]}
        assert got == {(p["giver_id"], p["giftee_id"]) for p in body["pairs"]}
        assert [p["name"] for p in loaded["participants"]] == ["Sam", "Alex", "Priya", "Jo", "Mia"]
        # One-way stays one-way: Jo -> Priya was never blocked.
        assert (five.ids["Jo"], five.ids["Priya"]) not in got
        summary = client.get("/admin/group", headers=bearer(five.admin)).json()
        assert summary["exclusion_pair_count"] == 2

    def test_put_replaces_everything(self, client, five):
        put(client, five, {"pairs": pairs(five, ("Sam", "Alex"))})
        put(client, five, {"pairs": pairs(five, ("Jo", "Mia"))})
        loaded = client.get(f"/groups/{five.id}/exclusions", headers=bearer(five.admin)).json()
        assert loaded["pairs"] == pairs(five, ("Jo", "Mia"))

    def test_duplicates_are_collapsed(self, client, five):
        body = {"pairs": pairs(five, ("Sam", "Alex"), ("Sam", "Alex"))}
        assert len(put(client, five, body).json()["pairs"]) == 1

    def test_show_exclusions_untouched_when_omitted(self, client, five):
        put(client, five, {"pairs": [], "show_exclusions": True})
        assert put(client, five, {"pairs": []}).json()["show_exclusions"] is True

    def test_rejects_self_and_outsiders(self, client, five, make_group):
        other = make_group(name="Other", admin_email="o@example.com")
        outsider = client.get("/admin/group", headers=bearer(other.admin)).json()["participants"][0]
        bad_bodies = [
            {"pairs": pairs(five, ("Sam", "Sam"))},
            {"pairs": [{"giver_id": five.ids["Sam"], "giftee_id": outsider["id"]}]},
        ]
        for body in bad_bodies:
            assert put(client, five, body).status_code == 422
            assert check(client, five, body).status_code == 422

    def test_admin_only_writes(self, client, five):
        body = {"pairs": []}
        for token in (five.tokens["Alex"], five.tokens["Sam"]):
            h = bearer(token)
            assert (
                client.put(f"/groups/{five.id}/exclusions", headers=h, json=body).status_code == 404
            )
            assert (
                client.post(f"/groups/{five.id}/exclusions/check", headers=h, json=body).status_code
                == 404
            )

    def test_wrong_group(self, client, five, make_group):
        other = make_group(name="Other", admin_email="o@example.com")
        assert put(client, other, {"pairs": []}).status_code == 200
        response = client.put(
            f"/groups/{five.id}/exclusions", headers=bearer(other.admin), json={"pairs": []}
        )
        assert response.status_code == 404


class TestParticipantVisibility:
    def test_hidden_by_default(self, client, five):
        put(client, five, {"pairs": pairs(five, ("Sam", "Alex"))})
        url = f"/groups/{five.id}/exclusions"
        assert client.get(url, headers=bearer(five.tokens["Alex"])).status_code == 404

    def test_visible_when_admin_allows(self, client, five):
        put(client, five, {"pairs": pairs(five, ("Sam", "Alex")), "show_exclusions": True})
        url = f"/groups/{five.id}/exclusions"
        response = client.get(url, headers=bearer(five.tokens["Alex"]))
        assert response.status_code == 200
        assert response.json()["pairs"] == pairs(five, ("Sam", "Alex"))
        assert "@" not in response.text  # names only, no emails


class TestCheck:
    def test_possible(self, client, five):
        body = {"pairs": pairs(five, ("Sam", "Alex"), ("Alex", "Sam"))}
        assert check(client, five, body).json() == {
            "possible": True,
            "reason": None,
            "bottleneck": None,
        }

    def test_impossible_names_the_bottleneck(self, client, five):
        # Sam and Alex can each only give to Mia.
        blocked = [("Sam", x) for x in ("Alex", "Priya", "Jo")] + [
            ("Alex", x) for x in ("Sam", "Priya", "Jo")
        ]
        result = check(client, five, {"pairs": pairs(five, *blocked)}).json()
        assert result["possible"] is False and result["reason"] == "stuck"
        assert result["bottleneck"] == {
            "side": "give",
            "people": sorted([five.ids["Sam"], five.ids["Alex"]]),
            "options": [five.ids["Mia"]],
        }

    def test_check_does_not_save(self, client, five):
        check(client, five, {"pairs": pairs(five, ("Sam", "Alex"))})
        loaded = client.get(f"/groups/{five.id}/exclusions", headers=bearer(five.admin)).json()
        assert loaded["pairs"] == []

    def test_too_few_people(self, client, outbox, make_group):
        g = make_group()
        result = client.post(
            f"/groups/{g.id}/exclusions/check", headers=bearer(g.admin), json={"pairs": []}
        ).json()
        assert result == {"possible": False, "reason": "too_few", "bottleneck": None}
