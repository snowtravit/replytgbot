import unittest

from settings import Config, ReplyCooldown


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.environment = {"API_ID": "123456", "API_HASH": "a" * 32}

    def test_minimal_config_works_without_media_or_other_environment_values(self):
        config = Config.from_env(self.environment)
        self.assertIsNone(config.photo_url)
        self.assertIsNone(config.gif_url)
        self.assertEqual(config.cooldown_seconds, 3600)
        self.assertTrue(config.reply_text)

    def test_missing_or_placeholder_credentials_fail_before_runtime(self):
        for overrides, expected in (
            ({"API_ID": ""}, "API_ID"),
            ({"API_ID": "0"}, "API_ID"),
            ({"API_ID": "-1"}, "API_ID"),
            ({"API_ID": "1.5"}, "API_ID"),
            ({"API_HASH": "your_api_hash"}, "API_HASH"),
            ({"API_HASH": "g" * 32}, "API_HASH"),
        ):
            with self.subTest(overrides=overrides):
                with self.assertRaisesRegex(ValueError, expected):
                    Config.from_env({**self.environment, **overrides})

    def test_configured_media_and_cooldown_are_preserved(self):
        config = Config.from_env(
            {
                **self.environment,
                "REPLY_TEXT": "I'll reply later.",
                "PHOTO_URL": "https://example.org/photo.jpg",
                "GIF_URL": "https://example.org/animation.gif",
                "COOLDOWN_SECONDS": "600",
                "SESSION_NAME": "my_session",
            }
        )
        self.assertEqual(config.reply_text, "I'll reply later.")
        self.assertEqual(config.photo_url, "https://example.org/photo.jpg")
        self.assertEqual(config.gif_url, "https://example.org/animation.gif")
        self.assertEqual(config.cooldown_seconds, 600)
        self.assertEqual(config.session_name, "my_session")

    def test_invalid_media_cooldown_or_empty_content_is_rejected(self):
        for name, values in (
            ("PHOTO_URL", ("photo.jpg", "https://", "file:///photo.jpg")),
            (
                "GIF_URL",
                (
                    "http://example.org/a.gif",
                    "https://user:password@example.org/a.gif",
                    "https://example.org:bad/a.gif",
                    "https://example.org/a gif",
                ),
            ),
            ("COOLDOWN_SECONDS", ("0", "-20", "one", "1.5", "")),
            ("SESSION_NAME", (" ",)),
            ("REPLY_TEXT", ("", "\n ")),
        ):
            for value in values:
                with self.subTest(name=name, value=value):
                    with self.assertRaisesRegex(ValueError, name):
                        Config.from_env({**self.environment, name: value})

    def test_photo_caption_limit_accounts_for_emoji(self):
        config = {**self.environment, "PHOTO_URL": "https://example.org/photo.jpg"}
        Config.from_env({**config, "REPLY_TEXT": "😀" * 512})
        with self.assertRaisesRegex(ValueError, "REPLY_TEXT"):
            Config.from_env({**config, "REPLY_TEXT": "😀" * 513})
        # The same text is valid when sent as a standalone message.
        Config.from_env({**self.environment, "REPLY_TEXT": "😀" * 513})

    def test_standalone_message_limit(self):
        Config.from_env({**self.environment, "REPLY_TEXT": "a" * 4096})
        with self.assertRaisesRegex(ValueError, "REPLY_TEXT"):
            Config.from_env({**self.environment, "REPLY_TEXT": "a" * 4097})


class CooldownTests(unittest.TestCase):
    def setUp(self):
        self.now = 100.0
        self.cooldown = ReplyCooldown(60, clock=lambda: self.now)

    def test_burst_is_skipped_but_other_sender_can_receive_a_reply(self):
        # Reserving before the send also covers in-flight and failed attempts.
        self.assertTrue(self.cooldown.reserve(1))
        self.assertFalse(self.cooldown.reserve(1))
        self.assertTrue(self.cooldown.reserve(2))
        self.assertFalse(self.cooldown.reserve(2))

    def test_skipped_messages_do_not_extend_the_cooldown(self):
        self.assertTrue(self.cooldown.reserve(1))
        self.cooldown.finish(1)
        self.now = 159.0
        self.assertFalse(self.cooldown.reserve(1))
        self.now = 160.0
        self.assertTrue(self.cooldown.reserve(1))
        self.assertFalse(self.cooldown.reserve(1))

    def test_slow_send_stays_reserved_when_the_cooldown_expires(self):
        self.assertTrue(self.cooldown.reserve(1))
        self.now += 61
        self.assertFalse(self.cooldown.reserve(1))
        self.assertTrue(self.cooldown.reserve(2))
        self.cooldown.finish(1)
        self.assertTrue(self.cooldown.reserve(1))

    def test_finish_preserves_the_remaining_cooldown(self):
        self.assertTrue(self.cooldown.reserve(1))
        self.cooldown.finish(1)
        self.cooldown.finish(1)
        self.assertFalse(self.cooldown.reserve(1))

    def test_flood_wait_applies_to_all_senders_and_does_not_queue_them(self):
        self.cooldown.pause(120)
        self.assertFalse(self.cooldown.reserve(1))
        self.assertFalse(self.cooldown.reserve(2))
        self.now += 119
        self.assertFalse(self.cooldown.reserve(3))
        self.now += 1
        self.assertTrue(self.cooldown.reserve(1))
        self.assertTrue(self.cooldown.reserve(2))

    def test_shorter_flood_wait_does_not_release_an_existing_pause_early(self):
        self.cooldown.pause(120)
        self.now += 30
        self.cooldown.pause(10)
        self.now = 219
        self.assertFalse(self.cooldown.reserve(1))
        self.now = 220
        self.assertTrue(self.cooldown.reserve(1))


if __name__ == "__main__":
    unittest.main()
