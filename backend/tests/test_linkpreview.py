"""Safety rules for the link preview fetcher. No real network access except a local
server that must be refused."""

import http.server
import threading
import time

import httpx
import pytest

from app.linkpreview import (
    MAX_BYTES,
    BlockedURL,
    check_url,
    fetch_preview,
    is_public_address,
    is_safe_image_url,
    parse_preview,
    system_resolver,
)

PUBLIC = "93.184.215.14"
HTML = (
    b"<html><head><title>Merino socks</title>"
    b"<meta property='og:image' content='/s.jpg'></head></html>"
)


def resolver(table: dict[str, list[str]]):
    def resolve(host: str, port: int) -> list[str]:
        if host not in table:
            raise OSError("no such host")
        return table[host]

    return resolve


PUBLIC_DNS = resolver({"shop.example": [PUBLIC], "cdn.example": ["151.101.1.1"]})


def transport(handler):
    return httpx.MockTransport(handler)


def html_response(body: bytes = HTML, status: int = 200, **headers) -> httpx.Response:
    return httpx.Response(
        status, content=body, headers={"content-type": "text/html; charset=utf-8", **headers}
    )


class TestAddressRules:
    @pytest.mark.parametrize(
        "address",
        [
            "127.0.0.1",
            "127.1.2.3",
            "10.0.0.1",
            "172.16.5.4",
            "192.168.1.1",
            "169.254.169.254",  # cloud metadata
            "100.64.0.1",  # carrier-grade NAT
            "0.0.0.0",
            "224.0.0.1",
            "255.255.255.255",
            "::1",
            "::",
            "fe80::1",
            "fe80::1%eth0",
            "fc00::1",
            "fd12:3456::1",
            "::ffff:127.0.0.1",  # IPv4-mapped loopback
            "::ffff:10.0.0.1",
            "ff02::1",
        ],
    )
    def test_private_and_special_addresses_are_refused(self, address):
        assert not is_public_address(address)

    @pytest.mark.parametrize("address", [PUBLIC, "8.8.8.8", "2606:4700:4700::1111"])
    def test_public_addresses_are_allowed(self, address):
        assert is_public_address(address)


class TestCheckURL:
    def test_allows_public_http_and_https(self):
        assert check_url("https://shop.example/socks", PUBLIC_DNS) == ("shop.example", PUBLIC)
        assert check_url("http://shop.example:80/socks", PUBLIC_DNS)[1] == PUBLIC

    @pytest.mark.parametrize(
        "url",
        [
            "ftp://shop.example/x",
            "file:///etc/passwd",
            "gopher://shop.example/",
            "https://user:pw@shop.example/",
            "https://shop.example:8443/",
            "http://shop.example:22/",
            "https://shop.example:99999/",
            "https:///nohost",
            "https://unknown.example/",
        ],
    )
    def test_refuses_bad_urls(self, url):
        with pytest.raises(BlockedURL):
            check_url(url, PUBLIC_DNS)

    @pytest.mark.parametrize(
        ("host", "addresses"),
        [
            ("localhost", ["127.0.0.1"]),
            ("internal.example", ["10.1.2.3"]),
            ("metadata.example", ["169.254.169.254"]),
            ("v6.example", ["::1"]),
            # A host with one public and one private address is refused outright.
            ("mixed.example", [PUBLIC, "192.168.0.10"]),
        ],
    )
    def test_refuses_hosts_resolving_to_private_addresses(self, host, addresses):
        with pytest.raises(BlockedURL):
            check_url(f"https://{host}/", resolver({host: addresses}))

    @pytest.mark.parametrize(
        "url",
        [
            "http://127.0.0.1/",
            "http://2130706433/",
            "http://0x7f.1/",
            "http://[::1]/",
            "http://[::ffff:7f00:1]/",
        ],
    )
    def test_refuses_ip_literals_and_odd_encodings_via_the_real_resolver(self, url):
        with pytest.raises(BlockedURL):
            check_url(url, system_resolver)


class TestFetch:
    def test_fetches_title_and_absolute_image(self):
        seen = []

        def handler(request):
            seen.append(request)
            return html_response()

        preview = fetch_preview(
            "https://shop.example/socks", resolve=PUBLIC_DNS, transport=transport(handler)
        )
        assert preview.title == "Merino socks"
        assert preview.image_url == "https://shop.example/s.jpg"
        # Connected to the checked IP, with the real host in the Host header and SNI.
        (request,) = seen
        assert request.url.host == PUBLIC
        assert request.headers["host"] == "shop.example"
        assert request.extensions["sni_hostname"] == "shop.example"

    def test_follows_a_safe_redirect(self):
        def handler(request):
            if request.headers["host"] == "shop.example":
                return httpx.Response(302, headers={"location": "https://cdn.example/page"})
            return html_response()

        preview = fetch_preview(
            "https://shop.example/", resolve=PUBLIC_DNS, transport=transport(handler)
        )
        assert preview.title == "Merino socks"

    @pytest.mark.parametrize(
        "location",
        [
            "http://127.0.0.1/admin",
            "http://169.254.169.254/latest/meta-data/",
            "http://[::1]/",
            "http://internal.example/",
            "file:///etc/passwd",
            "http://shop.example:2375/",
        ],
    )
    def test_refuses_redirects_to_private_or_bad_targets(self, location):
        fetched_hosts = []

        def handler(request):
            fetched_hosts.append(request.headers["host"])
            return httpx.Response(302, headers={"location": location})

        dns = resolver({"shop.example": [PUBLIC], "internal.example": ["10.0.0.5"]})
        preview = fetch_preview("https://shop.example/", resolve=dns, transport=transport(handler))
        assert preview.title is None
        assert fetched_hosts == ["shop.example"]

    def test_caps_redirects(self):
        hops = []

        def handler(request):
            hops.append(request.url.path)
            return httpx.Response(302, headers={"location": f"/hop{len(hops)}"})

        preview = fetch_preview(
            "https://shop.example/", resolve=PUBLIC_DNS, transport=transport(handler)
        )
        assert preview.title is None
        assert len(hops) == 4  # the first request plus three redirects

    def test_caps_response_size(self):
        read = []

        def stream():
            yield b"<title>Big page</title>"
            for _ in range(100):
                read.append(1)
                yield b"x" * 65536

        def handler(request):
            return httpx.Response(200, content=stream(), headers={"content-type": "text/html"})

        preview = fetch_preview(
            "https://shop.example/", resolve=PUBLIC_DNS, transport=transport(handler)
        )
        assert preview.title == "Big page"
        assert len(read) * 65536 <= MAX_BYTES + 65536

    def test_overall_deadline(self):
        def stream():
            yield b"<title>Slow"
            time.sleep(0.3)
            yield b" page</title>"

        def handler(request):
            return httpx.Response(200, content=stream(), headers={"content-type": "text/html"})

        start = time.monotonic()
        preview = fetch_preview(
            "https://shop.example/",
            resolve=PUBLIC_DNS,
            transport=transport(handler),
            deadline_seconds=0.1,
        )
        assert preview.title is None
        assert time.monotonic() - start < 1

    @pytest.mark.parametrize(
        "response",
        [
            httpx.Response(200, content=b"%PDF", headers={"content-type": "application/pdf"}),
            httpx.Response(
                404, content=b"<title>Not found</title>", headers={"content-type": "text/html"}
            ),
            httpx.Response(500),
            httpx.Response(302),  # redirect without a location
        ],
    )
    def test_non_html_or_error_responses_give_an_empty_preview(self, response):
        preview = fetch_preview(
            "https://shop.example/", resolve=PUBLIC_DNS, transport=transport(lambda r: response)
        )
        assert preview.title is None and preview.image_url is None

    def test_network_errors_give_an_empty_preview(self):
        def handler(request):
            raise httpx.ConnectTimeout("slow")

        assert (
            fetch_preview(
                "https://shop.example/", resolve=PUBLIC_DNS, transport=transport(handler)
            ).title
            is None
        )

    def test_refuses_a_real_local_server(self):
        hits = []

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                hits.append(self.path)
                self.send_response(200)
                self.send_header("content-type", "text/html")
                self.end_headers()
                self.wfile.write(b"<title>Internal admin</title>")

            def log_message(self, *args):
                pass

        server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            port = server.server_address[1]
            for url in (
                f"http://127.0.0.1:{port}/",
                "http://localhost/",
                f"http://localhost:{port}/",
            ):
                assert fetch_preview(url).title is None
            assert hits == []
        finally:
            server.shutdown()


class TestParsing:
    def test_prefers_open_graph(self):
        html = (
            "<title>Shop | Socks</title>"
            "<meta property='og:title' content='Merino &amp; wool socks'>"
        )
        assert parse_preview(html, "https://shop.example/").title == "Merino & wool socks"

    def test_collapses_whitespace_and_trims_length(self):
        html = f"<title>\n  A   {'b' * 300}\n</title>"
        title = parse_preview(html, "https://shop.example/").title
        assert title.startswith("A b") and len(title) == 200

    @pytest.mark.parametrize(
        "image",
        [
            "javascript:alert(1)",
            "data:image/png;base64,AAAA",
            "http://192.168.1.1/x.png",
            "http://localhost/x.png",
        ],
    )
    def test_drops_unsafe_images(self, image):
        html = f"<meta property='og:image' content='{image}'>"
        assert parse_preview(html, "https://shop.example/").image_url is None

    def test_garbage_html(self):
        assert parse_preview("<<<>>><title", "https://shop.example/").title is None


class TestImageURL:
    @pytest.mark.parametrize("url", ["https://cdn.example/a.png", "http://8.8.8.8/a.png"])
    def test_allowed(self, url):
        assert is_safe_image_url(url)

    @pytest.mark.parametrize(
        "url",
        [
            "http://10.0.0.1/a.png",
            "http://[::1]/a.png",
            "http://localhost/a.png",
            "http://app.localhost/a",
            "ftp://x/a",
        ],
    )
    def test_refused(self, url):
        assert not is_safe_image_url(url)
