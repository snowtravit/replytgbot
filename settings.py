"""Configuration and reply timing, without Telegram or third-party imports."""

from dataclasses import dataclass
import re
import time
from typing import Callable, Mapping
from urllib.parse import urlsplit


def _positive_integer(value: str, name: str) -> int:
    try:
        number = int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a positive integer.") from exc
    if number <= 0:
        raise ValueError(f"{name} must be a positive integer.")
    return number


def _media_url(value: str, name: str) -> str | None:
    value = value.strip()
    if not value:
        return None
    try:
        url = urlsplit(value)
        valid = (
            url.scheme == "https"
            and bool(url.hostname)
            and url.username is None
            and url.password is None
            and not any(character.isspace() for character in value)
        )
        # Accessing port also validates malformed ports in the URL.
        url.port
    except ValueError:
        valid = False
    if not valid:
        raise ValueError(f"{name} must be an absolute HTTPS URL, or empty.")
    return value


@dataclass(frozen=True)
class Config:
    api_id: int
    api_hash: str
    session_name: str
    reply_text: str
    photo_url: str | None
    gif_url: str | None
    cooldown_seconds: int

    @classmethod
    def from_env(cls, environment: Mapping[str, str]) -> "Config":
        api_id = _positive_integer(environment.get("API_ID", ""), "API_ID")
        api_hash = environment.get("API_HASH", "").strip()
        if not re.fullmatch(r"[0-9a-fA-F]{32}", api_hash):
            raise ValueError("API_HASH must contain exactly 32 hexadecimal characters.")

        session_name = environment.get("SESSION_NAME", "replytgbot").strip()
        if not session_name:
            raise ValueError("SESSION_NAME must not be empty.")
        reply_text = environment.get(
            "REPLY_TEXT", "Thanks for your message! I will reply when I am available."
        ).strip()
        photo_url = _media_url(environment.get("PHOTO_URL", ""), "PHOTO_URL")
        gif_url = _media_url(environment.get("GIF_URL", ""), "GIF_URL")
        # Telegram measures text limits in UTF-16 code units, including emoji.
        text_length = len(reply_text.encode("utf-16-le")) // 2
        limit = 1024 if photo_url else 4096
        if not 1 <= text_length <= limit:
            raise ValueError(f"REPLY_TEXT must contain 1–{limit} UTF-16 code units.")

        return cls(
            api_id=api_id,
            api_hash=api_hash,
            session_name=session_name,
            reply_text=reply_text,
            photo_url=photo_url,
            gif_url=gif_url,
            cooldown_seconds=_positive_integer(
                environment.get("COOLDOWN_SECONDS", "3600"), "COOLDOWN_SECONDS"
            ),
        )


class ReplyCooldown:
    """Reserve an attempt before sending, so overlapping events cannot duplicate it."""

    def __init__(self, seconds: int, clock: Callable[[], float] = time.monotonic):
        if seconds <= 0:
            raise ValueError("Cooldown must be positive.")
        self._seconds = seconds
        self._clock = clock
        self._expires: dict[int, float] = {}
        self._active: set[int] = set()
        self._paused_until = 0.0

    def reserve(self, sender_id: int) -> bool:
        now = self._clock()
        self._expires = {
            sender: expiry for sender, expiry in self._expires.items() if expiry > now
        }
        if (
            now < self._paused_until
            or sender_id in self._expires
            or sender_id in self._active
        ):
            return False
        self._expires[sender_id] = now + self._seconds
        self._active.add(sender_id)
        return True

    def finish(self, sender_id: int) -> None:
        """Release an in-flight attempt while preserving its cooldown."""
        self._active.discard(sender_id)

    def pause(self, seconds: int) -> None:
        """Apply Telegram's flood wait to all senders without blocking the handler."""
        self._paused_until = max(self._paused_until, self._clock() + seconds)
