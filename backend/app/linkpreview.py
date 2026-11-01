"""Fetch a page title and image for a pasted wish-list link, without becoming an SSRF hole.

Rules:
- http and https only, default ports only, no credentials in the URL.
- Every address the host resolves to must be public. Private, loopback, link-local,
  shared, multicast and reserved ranges are refused, including IPv4-mapped IPv6.
- We connect to the address we checked (not a fresh DNS lookup), so DNS rebinding
  can't swap in a private address between the check and the request. TLS still
  verifies the certificate against the original hostname via SNI.
- Redirects are followed by hand, at most MAX_REDIRECTS, and each hop is checked again.
- One deadline covers the whole fetch, and at most MAX_BYTES of the body are read.
- Any failure returns an empty preview. Saving an item never depends on this.
"""

import contextlib
import ipaddress
import socket
import time
from collections.abc import Callable
from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

import httpx

MAX_REDIRECTS = 3
MAX_BYTES = 512 * 1024
DEADLINE_SECONDS = 5.0
USER_AGENT = "SecretSantaLinkPreview/1.0"
DEFAULT_PORTS = {"http": 80, "https": 443}

Resolver = Callable[[str, int], list[str]]


class BlockedURL(Exception):
    pass


@dataclass(frozen=True)
class Preview:
    title: str | None = None
    image_url: str | None = None


def system_resolver(host: str, port: int) -> list[str]:
    infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return list(dict.fromkeys(str(info[4][0]) for info in infos))


def is_public_address(address: str) -> bool:
    ip = ipaddress.ip_address(address.split("%", 1)[0])
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return ip.is_global and not ip.is_multicast


def is_safe_image_url(url: str) -> bool:
    """Images load in the giver's browser, so refuse IP literals that point at private
    networks. Hostnames are left alone: the browser resolves those, not us."""
    parts = urlsplit(url)
    if parts.scheme not in DEFAULT_PORTS or not parts.hostname or len(url) > 2048:
        return False
    try:
        return is_public_address(parts.hostname)
    except ValueError:
        return parts.hostname.lower() != "localhost" and not parts.hostname.endswith(".localhost")


def check_url(url: str, resolve: Resolver) -> tuple[str, str]:
    """Return (hostname, a safe IP to connect to) or raise BlockedURL."""
    parts = urlsplit(url)
    if parts.scheme not in DEFAULT_PORTS:
        raise BlockedURL("scheme")
    if parts.username or parts.password:
        raise BlockedURL("credentials")
    host = parts.hostname
    if not host:
        raise BlockedURL("host")
    try:
        port = parts.port
    except ValueError as exc:
        raise BlockedURL("port") from exc
    if port not in (None, DEFAULT_PORTS[parts.scheme]):
        raise BlockedURL("port")
    try:
        addresses = resolve(host, DEFAULT_PORTS[parts.scheme])
    except (OSError, UnicodeError) as exc:
        raise BlockedURL("dns") from exc
    if not addresses or not all(is_public_address(a) for a in addresses):
        raise BlockedURL("address")
    return host, addresses[0]


def _pinned_request(client: httpx.Client, url: str, host: str, ip: str) -> httpx.Request:
    parts = urlsplit(url)
    ip_host = f"[{ip}]" if ":" in ip else ip
    pinned = parts._replace(netloc=ip_host).geturl()
    headers = {"Host": parts.netloc, "User-Agent": USER_AGENT, "Accept": "text/html"}
    extensions = {"sni_hostname": host} if parts.scheme == "https" else {}
    return client.build_request("GET", pinned, headers=headers, extensions=extensions)


class _MetaParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.in_title = False
        self.meta: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "title":
            self.in_title = True
        elif tag == "meta":
            a = {k.lower(): (v or "") for k, v in attrs}
            key = (a.get("property") or a.get("name") or "").lower()
            if key in ("og:title", "og:image", "twitter:title", "twitter:image") and a.get(
                "content"
            ):
                self.meta.setdefault(key, a["content"])

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_parts.append(data)


def parse_preview(html: str, base_url: str) -> Preview:
    parser = _MetaParser()
    with contextlib.suppress(Exception):  # malformed HTML just means a weaker preview
        parser.feed(html)
    title = parser.meta.get("og:title") or parser.meta.get("twitter:title")
    title = title or "".join(parser.title_parts)
    title = " ".join(unescape(title).split())[:200] or None

    image = parser.meta.get("og:image") or parser.meta.get("twitter:image")
    image_url = None
    if image:
        candidate = urljoin(base_url, image.strip())
        if is_safe_image_url(candidate):
            image_url = candidate
    return Preview(title=title, image_url=image_url)


def fetch_preview(
    url: str,
    *,
    resolve: Resolver = system_resolver,
    transport: httpx.BaseTransport | None = None,
    deadline_seconds: float = DEADLINE_SECONDS,
) -> Preview:
    try:
        return _fetch(url, resolve, transport, deadline_seconds)
    except Exception:
        return Preview()


def _fetch(
    url: str,
    resolve: Resolver,
    transport: httpx.BaseTransport | None,
    deadline_seconds: float,
) -> Preview:
    deadline = time.monotonic() + deadline_seconds
    timeout = httpx.Timeout(deadline_seconds, connect=min(3.0, deadline_seconds))
    with httpx.Client(transport=transport, timeout=timeout, follow_redirects=False) as client:
        for _ in range(MAX_REDIRECTS + 1):
            if time.monotonic() > deadline:
                return Preview()
            host, ip = check_url(url, resolve)
            request = _pinned_request(client, url, host, ip)
            response = client.send(request, stream=True)
            try:
                if response.is_redirect:
                    location = response.headers.get("location")
                    if not location:
                        return Preview()
                    url = urljoin(url, location)
                    continue
                if response.status_code != 200:
                    return Preview()
                if "html" not in response.headers.get("content-type", "").lower():
                    return Preview()
                body = bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if len(body) >= MAX_BYTES:
                        break
                    if time.monotonic() > deadline:
                        return Preview()
                encoding = response.encoding or "utf-8"
                html = bytes(body[:MAX_BYTES]).decode(encoding, errors="replace")
                return parse_preview(html, url)
            finally:
                response.close()
        return Preview()  # too many redirects
