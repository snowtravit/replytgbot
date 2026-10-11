"""Exercise delivery and event handling without connecting to Telegram."""

import asyncio
from dataclasses import replace
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from telethon.errors import FloodWaitError
from telethon.tl.functions.messages import SendMediaRequest
from telethon.tl.types import InputMediaPhotoExternal

from settings import Config, ReplyCooldown
from tgbot import main, send_reply


def configured(**overrides):
    return replace(
        Config.from_env({"API_ID": "123456", "API_HASH": "a" * 32}), **overrides
    )


def incoming(sender=1, private=True):
    return SimpleNamespace(sender_id=sender, chat_id=sender, is_private=private)


class DeliveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_plain_text_is_not_interpreted_as_markup(self):
        client = AsyncMock()
        config = configured(reply_text="**literal text** <b>hello</b>")
        await send_reply(client, 1, config)
        client.send_message.assert_awaited_once_with(
            1, config.reply_text, parse_mode=None
        )
        client.assert_not_awaited()

    async def test_rejected_photo_falls_back_once_without_logging_private_data(self):
        client = AsyncMock(side_effect=RuntimeError("private recipient details"))
        config = configured(photo_url="https://example.org/photo.jpg")
        with self.assertLogs("tgbot", level="WARNING") as output:
            await send_reply(client, 1, config)
        request = client.await_args.args[0]
        self.assertIsInstance(request, SendMediaRequest)
        self.assertIsInstance(request.media, InputMediaPhotoExternal)
        client.send_message.assert_awaited_once_with(
            1, config.reply_text, parse_mode=None
        )
        self.assertNotIn("private recipient details", " ".join(output.output))

    async def test_photo_flood_wait_does_not_trigger_another_send(self):
        client = AsyncMock(side_effect=FloodWaitError(None, 10))
        config = configured(
            photo_url="https://example.org/photo.jpg",
            gif_url="https://example.org/animation.gif",
        )
        with self.assertRaises(FloodWaitError):
            await send_reply(client, 1, config)
        self.assertEqual(client.await_count, 1)
        client.send_message.assert_not_awaited()

    async def test_failed_text_stops_delivery_before_the_gif(self):
        client = AsyncMock()
        client.send_message.side_effect = RuntimeError("delivery failed")
        with self.assertRaises(RuntimeError):
            await send_reply(
                client, 1, configured(gif_url="https://example.org/animation.gif")
            )
        client.assert_not_awaited()


class OfflineClient:
    def __init__(self, flow):
        self.flow = flow
        self.start = AsyncMock()
        self.disconnect = AsyncMock()

    def on(self, event_filter):
        def register(handler):
            self.handler = handler
            return handler

        return register

    async def run_until_disconnected(self):
        await self.flow(self.handler)


class HandlerTests(unittest.IsolatedAsyncioTestCase):
    async def exercise(self, flow, delivery):
        client = OfflineClient(flow)
        cooldown = ReplyCooldown(1, clock=lambda: self.now)
        config = configured(cooldown_seconds=1)
        with (
            patch("tgbot.TelegramClient", return_value=client) as client_factory,
            patch("tgbot.ReplyCooldown", return_value=cooldown),
            patch("tgbot.send_reply", delivery),
        ):
            await main(config)
        client_factory.assert_called_once_with(
            config.session_name,
            config.api_id,
            config.api_hash,
            flood_sleep_threshold=0,
        )
        client.disconnect.assert_awaited_once()

    def setUp(self):
        self.now = 0.0

    async def test_slow_reply_never_overlaps_another_reply_to_the_same_sender(self):
        started = asyncio.Event()
        finish = asyncio.Event()

        async def blocked_delivery(*args):
            started.set()
            await finish.wait()

        delivery = AsyncMock(side_effect=blocked_delivery)

        async def flow(handler):
            first = asyncio.create_task(handler(incoming()))
            try:
                await asyncio.wait_for(started.wait(), 1)
                self.now = 2.0
                await handler(incoming())
                self.assertEqual(delivery.await_count, 1)
            finally:
                finish.set()
                await first
            await handler(incoming())
            self.assertEqual(delivery.await_count, 2)

        await self.exercise(flow, delivery)

    async def test_failed_reply_releases_inflight_reservation(self):
        delivery = AsyncMock(side_effect=[RuntimeError("send failed"), None])

        async def flow(handler):
            with self.assertLogs("tgbot", level="WARNING"):
                await handler(incoming())
            self.now = 2.0
            await handler(incoming())
            self.assertEqual(delivery.await_count, 2)

        await self.exercise(flow, delivery)

    async def test_flood_wait_pauses_every_sender_and_later_resumes(self):
        delivery = AsyncMock(side_effect=[FloodWaitError(None, 10), None])

        async def flow(handler):
            with self.assertLogs("tgbot", level="WARNING"):
                await handler(incoming())
            self.now = 10.0
            await handler(incoming(2))
            self.assertEqual(delivery.await_count, 1)
            self.now = 11.0
            await handler(incoming(2))
            self.assertEqual(delivery.await_count, 2)

        await self.exercise(flow, delivery)

    async def test_group_and_unidentified_messages_are_ignored(self):
        delivery = AsyncMock()

        async def flow(handler):
            await handler(incoming(private=False))
            await handler(incoming(sender=None))
            delivery.assert_not_awaited()

        await self.exercise(flow, delivery)


if __name__ == "__main__":
    unittest.main()
