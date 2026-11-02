import pytest

from app import linkpreview
from app.linkpreview import Preview
from tests.conftest import bearer, join


@pytest.fixture
def alex(client, outbox, make_group):
    g = make_group()
    return join(client, outbox, g.invite, "Alex", "alex@example.com")


def add(client, token, **item):
    response = client.post("/me/items", headers=bearer(token), json=item)
    assert response.status_code == 201, response.text
    return response.json()


def items(client, token):
    return client.get("/me", headers=bearer(token)).json()["items"]


class TestItems:
    def test_add_with_and_without_link(self, client, alex):
        a = add(
            client, alex, title="Merino wool socks", url="https://johnlewis.com/socks", price=1800
        )
        b = add(client, alex, title="  Surprise me  ")
        assert a["price"] == 1800 and a["url"] == "https://johnlewis.com/socks"
        assert b == {
            "id": b["id"],
            "title": "Surprise me",
            "url": None,
            "price": None,
            "image_url": None,
        }
        assert [i["title"] for i in items(client, alex)] == ["Merino wool socks", "Surprise me"]

    @pytest.mark.parametrize(
        "bad",
        [
            {"title": ""},
            {"title": "x" * 201},
            {"title": "A", "url": "javascript:alert(1)"},
            {"title": "A", "url": "ftp://example.com/x"},
            {"title": "A", "url": "https://user:pw@example.com/"},
            {"title": "A", "price": -1},
            {"title": "A", "image_url": "http://192.168.1.1/x.png"},
            {"title": "A", "image_url": "http://localhost/x.png"},
            {"title": "A", "participant_id": 1},
        ],
    )
    def test_validation(self, client, alex, bad):
        assert client.post("/me/items", headers=bearer(alex), json=bad).status_code == 422

    def test_edit(self, client, alex):
        item = add(
            client,
            alex,
            title="Socks",
            url="https://a.example/1",
            price=1000,
            image_url="https://cdn.example/a.png",
        )
        response = client.patch(
            f"/me/items/{item['id']}",
            headers=bearer(alex),
            json={"price": 3200, "title": "Wool socks"},
        )
        assert response.json()["price"] == 3200 and response.json()["title"] == "Wool socks"
        assert response.json()["image_url"] == "https://cdn.example/a.png"

        # Changing the link drops the old preview image; clearing the price works.
        response = client.patch(
            f"/me/items/{item['id']}",
            headers=bearer(alex),
            json={"url": "https://b.example/2", "price": None},
        )
        body = response.json()
        assert (
            body["url"] == "https://b.example/2"
            and body["image_url"] is None
            and body["price"] is None
        )

        # The title can't be cleared.
        response = client.patch(
            f"/me/items/{item['id']}", headers=bearer(alex), json={"title": None}
        )
        assert response.json()["title"] == "Wool socks"

    def test_delete(self, client, alex):
        a = add(client, alex, title="A")
        add(client, alex, title="B")
        assert client.delete(f"/me/items/{a['id']}", headers=bearer(alex)).status_code == 204
        assert [i["title"] for i in items(client, alex)] == ["B"]

    def test_reorder(self, client, alex):
        ids = [add(client, alex, title=t)["id"] for t in "ABC"]
        response = client.put(
            "/me/items/order", headers=bearer(alex), json={"ids": [ids[2], ids[0], ids[1]]}
        )
        assert response.status_code == 200
        assert [i["title"] for i in items(client, alex)] == ["C", "A", "B"]
        # New items go to the end.
        add(client, alex, title="D")
        assert [i["title"] for i in items(client, alex)] == ["C", "A", "B", "D"]

    def test_reorder_must_list_every_own_item_once(self, client, outbox, make_group, alex):
        ids = [add(client, alex, title=t)["id"] for t in "AB"]
        for bad in ([ids[0]], [ids[0], ids[0]], [ids[0], ids[1], 999]):
            assert (
                client.put("/me/items/order", headers=bearer(alex), json={"ids": bad}).status_code
                == 422
            )

    def test_cannot_touch_someone_elses_items(self, client, outbox, make_group):
        g = make_group()
        alex = join(client, outbox, g.invite, "Alex", "alex@example.com")
        priya = join(client, outbox, g.invite, "Priya", "priya@example.com")
        item = add(client, alex, title="Mine")
        for response in (
            client.patch(f"/me/items/{item['id']}", headers=bearer(priya), json={"title": "Ha"}),
            client.delete(f"/me/items/{item['id']}", headers=bearer(priya)),
            client.put("/me/items/order", headers=bearer(priya), json={"ids": [item["id"]]}),
        ):
            assert response.status_code in (404, 422)
        assert items(client, alex)[0]["title"] == "Mine"

    def test_admin_token_cannot_edit_wish_lists_when_not_taking_part(self, client, make_group):
        g = make_group(admin_participates=False)
        assert (
            client.post("/me/items", headers=bearer(g.admin), json={"title": "A"}).status_code
            == 404
        )

    def test_item_cap(self, client, alex, monkeypatch):
        monkeypatch.setattr("app.routers.me.MAX_ITEMS", 2)
        add(client, alex, title="A")
        add(client, alex, title="B")
        assert (
            client.post("/me/items", headers=bearer(alex), json={"title": "C"}).status_code == 409
        )


class TestProfile:
    def test_secret_surprise_and_rename(self, client, outbox, make_group, alex):
        response = client.put(
            "/me", headers=bearer(alex), json={"secret_surprise": True, "name": " Alexandra "}
        )
        assert response.status_code == 200
        assert response.json()["secret_surprise"] is True and response.json()["name"] == "Alexandra"
        assert client.put("/me", headers=bearer(alex), json={"name": ""}).status_code == 422

    def test_wish_list_in_status(self, client, outbox, make_group):
        g = make_group()
        alex = join(client, outbox, g.invite, "Alex", "alex@example.com")
        priya = join(client, outbox, g.invite, "Priya", "priya@example.com")

        def statuses():
            people = client.get("/admin/group", headers=bearer(g.admin)).json()["participants"]
            return {p["name"]: p["status"] for p in people}

        assert statuses() == {"Sam": "joined", "Alex": "joined", "Priya": "joined"}
        add(client, alex, title="Socks")
        client.put("/me", headers=bearer(priya), json={"secret_surprise": True})
        assert statuses() == {"Sam": "joined", "Alex": "wish_list_in", "Priya": "wish_list_in"}

    def test_other_participants_and_admin_never_see_a_wish_list(self, client, outbox, make_group):
        g = make_group()
        alex = join(client, outbox, g.invite, "Alex", "alex@example.com")
        priya = join(client, outbox, g.invite, "Priya", "priya@example.com")
        add(client, alex, title="Very secret socks", url="https://shop.example/secret")
        for token in (g.admin, priya, g.admin_participant):
            for path in ("/admin/group", f"/groups/{g.id}", "/me"):
                text = client.get(path, headers=bearer(token)).text
                assert "Very secret socks" not in text and "shop.example" not in text


class TestLinkPreviewEndpoint:
    def test_returns_preview(self, client, alex, monkeypatch):
        monkeypatch.setattr(
            "app.routers.me.fetch_preview",
            lambda url: Preview(title="Merino socks", image_url="https://cdn.example/s.jpg"),
        )
        response = client.post(
            "/link-preview", headers=bearer(alex), json={"url": "https://shop.example/socks"}
        )
        assert response.json() == {
            "title": "Merino socks",
            "image_url": "https://cdn.example/s.jpg",
        }

    def test_blocked_url_returns_empty_preview_not_an_error(self, client, alex):
        response = client.post(
            "/link-preview", headers=bearer(alex), json={"url": "http://127.0.0.1:8000/admin/group"}
        )
        assert response.status_code == 200
        assert response.json() == {"title": None, "image_url": None}

    def test_requires_participant_token(self, client, make_group):
        g = make_group(admin_participates=False)
        response = client.post(
            "/link-preview", headers=bearer(g.admin), json={"url": "https://example.com"}
        )
        assert response.status_code == 404

    def test_rate_limited_quietly(self, client, alex, monkeypatch):
        from app.config import get_settings

        calls = []
        monkeypatch.setattr(
            "app.routers.me.fetch_preview", lambda url: calls.append(url) or Preview(title="T")
        )
        monkeypatch.setattr(get_settings(), "rate_limit_link_preview", 2)
        bodies = [
            client.post(
                "/link-preview", headers=bearer(alex), json={"url": "https://example.com"}
            ).json()
            for _ in range(3)
        ]
        assert [b["title"] for b in bodies] == ["T", "T", None]
        assert len(calls) == 2

    def test_saving_never_depends_on_preview(self, client, alex, monkeypatch):
        def boom(*args, **kwargs):
            raise AssertionError("saving must not fetch")

        monkeypatch.setattr(linkpreview, "fetch_preview", boom)
        monkeypatch.setattr("app.routers.me.fetch_preview", boom)
        add(client, alex, title="Offline shop", url="http://10.0.0.1/item")
