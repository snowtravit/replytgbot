"""Auto-reply to incoming private messages from a Telegram user account."""

import asyncio
import logging
import os

from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError
from telethon.tl.functions.messages import SendMediaRequest
from telethon.tl.types import InputMediaDocumentExternal, InputMediaPhotoExternal

from settings import Config, ReplyCooldown


logger = logging.getLogger(__name__)


async def send_reply(client: TelegramClient, chat_id: int, config: Config) -> None:
    if config.photo_url:
        try:
            await client(
                SendMediaRequest(
                    peer=chat_id,
                    media=InputMediaPhotoExternal(url=config.photo_url),
                    message=config.reply_text,
                )
            )
        except FloodWaitError:
            raise
        except Exception as exc:
            logger.warning(
                "Photo delivery failed (%s); sending text instead.", type(exc).__name__
            )
            await client.send_message(chat_id, config.reply_text, parse_mode=None)
    else:
        await client.send_message(chat_id, config.reply_text, parse_mode=None)

    if config.gif_url:
        try:
            await client(
                SendMediaRequest(
                    peer=chat_id,
                    media=InputMediaDocumentExternal(url=config.gif_url),
                    message="",
                )
            )
        except FloodWaitError:
            raise
        except Exception as exc:
            logger.warning("GIF delivery failed (%s).", type(exc).__name__)


async def main(config: Config) -> None:
    client = TelegramClient(
        config.session_name,
        config.api_id,
        config.api_hash,
        # Handle every flood wait here instead of Telethon sleeping and retrying
        # inside a send while other incoming messages continue to be processed.
        flood_sleep_threshold=0,
    )
    cooldown = ReplyCooldown(config.cooldown_seconds)

    @client.on(events.NewMessage(incoming=True))
    async def handler(event):
        if not event.is_private or event.sender_id is None:
            return
        if not cooldown.reserve(event.sender_id):
            return

        try:
            await send_reply(client, event.chat_id, config)
            logger.info("Auto-reply attempt completed.")
        except FloodWaitError as exc:
            # Pause all replies; incoming messages during the pause are not queued.
            cooldown.pause(exc.seconds + 1)
            logger.warning("Telegram requested a pause of %s seconds.", exc.seconds)
        except Exception as exc:
            logger.warning("Auto-reply failed (%s).", type(exc).__name__)
        finally:
            cooldown.finish(event.sender_id)

    try:
        await client.start()
        logger.info(
            "Auto-reply is running; per-sender cooldown is %s seconds.",
            config.cooldown_seconds,
        )
        await client.run_until_disconnected()
    finally:
        await client.disconnect()


def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    # Values exported by the shell take precedence over .env.
    load_dotenv(override=False)
    try:
        config = Config.from_env(os.environ)
    except ValueError as exc:
        logger.error("Configuration error: %s", exc)
        raise SystemExit(2) from None

    try:
        asyncio.run(main(config))
    except KeyboardInterrupt:
        logger.info("Auto-reply stopped.")
    except Exception as exc:
        logger.error(
            "Telegram connection failed (%s). Check credentials, session and network.",
            type(exc).__name__,
        )
        raise SystemExit(1) from None


if __name__ == "__main__":
    run()
