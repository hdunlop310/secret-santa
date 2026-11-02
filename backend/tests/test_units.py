"""Unit tests that need no database."""

import base64
import io
from contextlib import redirect_stdout

import pytest
from fastapi import HTTPException

from app.email.senders import ConsoleEmailSender, EmailMessage, redact_links, send_safely
from app.money import format_budget, format_pence
from app.ratelimit import RateLimiter
from app.security import hash_token, new_token, tokens_match


class TestTokens:
    def test_tokens_are_at_least_128_bits_and_url_safe(self):
        token = new_token()
        raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
        assert len(raw) * 8 >= 128
        assert all(c.isalnum() or c in "-_" for c in token)

    def test_tokens_are_unique(self):
        assert len({new_token() for _ in range(1000)}) == 1000

    def test_hash_is_sha256_hex_and_not_the_token(self):
        token = new_token()
        digest = hash_token(token)
        assert len(digest) == 64 and digest != token
        assert hash_token(token) == digest

    def test_tokens_match(self):
        token = new_token()
        assert tokens_match(token, hash_token(token))
        assert not tokens_match(new_token(), hash_token(token))


class TestMoney:
    @pytest.mark.parametrize(
        ("pence", "text"),
        [(0, "£0"), (1800, "£18"), (1850, "£18.50"), (1805, "£18.05"), (99, "£0.99")],
    )
    def test_format_pence(self, pence, text):
        assert format_pence(pence) == text

    def test_format_budget(self):
        assert format_budget(1500, 2500) == "£15 to £25"


class TestRateLimiter:
    def test_blocks_after_limit_within_window(self):
        limiter = RateLimiter(window_seconds=60)
        assert all(limiter.hit("b", "k", 3, now=t) for t in (0, 1, 2))
        assert not limiter.hit("b", "k", 3, now=3)

    def test_window_slides(self):
        limiter = RateLimiter(window_seconds=60)
        for t in (0, 1, 2):
            limiter.hit("b", "k", 3, now=t)
        assert limiter.hit("b", "k", 3, now=61)

    def test_keys_and_buckets_are_separate(self):
        limiter = RateLimiter(window_seconds=60)
        limiter.hit("b", "k", 1, now=0)
        assert limiter.hit("b", "other", 1, now=0)
        assert limiter.hit("other", "k", 1, now=0)

    def test_check_raises_429(self):
        limiter = RateLimiter()
        limiter.check("b", "k", 1)
        with pytest.raises(HTTPException) as exc:
            limiter.check("b", "k", 1)
        assert exc.value.status_code == 429


class TestEmailSafety:
    def test_redacts_admin_and_personal_links(self):
        token = new_token()
        text = f"admin https://x.test/g/{token} and http://localhost:5173/p/{token}."
        redacted = redact_links(text)
        assert token not in redacted
        assert redacted.count("[private link]") == 2

    def test_console_sender_never_prints_tokens(self):
        token = new_token()
        message = EmailMessage("a@example.com", "Hi", f"Link: http://h/p/{token}", "")
        out = io.StringIO()
        with redirect_stdout(out):
            ConsoleEmailSender().send(message)
        assert token not in out.getvalue()

    def test_send_safely_swallows_and_logs_without_body(self, caplog):
        token = new_token()

        class Broken:
            def send(self, message):
                raise ConnectionError(f"boom {message.text}")

        send_safely(Broken(), EmailMessage("a@example.com", "S", f"http://h/p/{token}", ""))
        assert token not in caplog.text
        assert "ConnectionError" in caplog.text


class TestClientIp:
    def request(self, forwarded=None, peer="10.0.0.9"):
        from starlette.requests import Request

        headers = [(b"x-forwarded-for", forwarded.encode())] if forwarded else []
        return Request({"type": "http", "headers": headers, "client": (peer, 1234)})

    def test_without_proxies_uses_the_peer_and_ignores_headers(self, monkeypatch):
        from app.config import get_settings
        from app.ratelimit import client_ip

        monkeypatch.setattr(get_settings(), "trusted_proxy_hops", 0)
        assert client_ip(self.request("1.2.3.4")) == "10.0.0.9"

    def test_one_proxy_takes_the_rightmost_entry(self, monkeypatch):
        from app.config import get_settings
        from app.ratelimit import client_ip

        monkeypatch.setattr(get_settings(), "trusted_proxy_hops", 1)
        # A client trying to spoof its address only controls the left-hand entries.
        assert client_ip(self.request("6.6.6.6, 203.0.113.7")) == "203.0.113.7"
        assert client_ip(self.request("203.0.113.7")) == "203.0.113.7"
        assert client_ip(self.request()) == "10.0.0.9"


class TestDatabaseUrl:
    def test_hosted_urls_get_the_psycopg_driver(self):
        from app.config import Settings

        for url in ("postgres://u:p@h:5432/db", "postgresql://u:p@h:5432/db"):
            assert Settings(database_url=url).database_url == "postgresql+psycopg://u:p@h:5432/db"
        ours = "postgresql+psycopg://u:p@h/db"
        assert Settings(database_url=ours).database_url == ours
