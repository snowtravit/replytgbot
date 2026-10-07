# Telegram Auto-Reply

[![Checks](https://github.com/snowtravit/replytgbot/actions/workflows/checks.yml/badge.svg)](https://github.com/snowtravit/replytgbot/actions/workflows/checks.yml)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue)

A small [Telethon](https://docs.telethon.dev/) userbot that replies to incoming
private messages from your **Telegram user account**. It sends configurable text
and optional photo/GIF URLs. Groups, channels and outgoing messages are ignored.
It sends existing media; it does not generate or process images.

## Setup

Requires Python 3.10 or newer and a Telegram account.

```bash
git clone https://github.com/snowtravit/replytgbot.git
cd replytgbot
python -m venv .venv
source .venv/bin/activate
python -m pip install -r req.txt
cp .env.example .env
```

On Windows, activate with `.venv\Scripts\activate` and copy the file with
`copy .env.example .env`.

Create your API credentials at [my.telegram.org/apps](https://my.telegram.org/apps)
and replace `API_ID` and `API_HASH` in `.env`. These are user-account API
credentials, not a BotFather token.

```bash
python tgbot.py
```

The first run asks for your phone number, Telegram login code, and two-step
verification password if enabled. Later runs use the local `.session` file.
Keep `.env` and session files private: the session grants access to your account.
They are excluded from Git. Stop the process with Ctrl+C.

## Configuration

Values come from `.env` or exported environment variables; exported variables
take precedence. Configuration is validated before connecting to Telegram.

| Variable | Purpose | Default |
| --- | --- | --- |
| `API_ID` | Positive integer from Telegram | Required |
| `API_HASH` | 32-character hexadecimal API hash | Required |
| `SESSION_NAME` | Local session filename or path | `replytgbot` |
| `REPLY_TEXT` | Plain-text response, or photo caption | “Thanks for your message! I will reply when I am available.” |
| `PHOTO_URL` | Direct, publicly accessible HTTPS photo URL | Empty |
| `GIF_URL` | Direct, publicly accessible HTTPS GIF URL | Empty |
| `COOLDOWN_SECONDS` | Positive integer between reply attempts to each sender | `3600` |

With a photo configured, the response text becomes its caption. If Telegram
rejects the photo, the userbot attempts a text response instead. A configured
GIF is sent as a separate message after the text/photo. Media URLs must point
to files Telegram can fetch, rather than pages with download buttons; delivery
still depends on Telegram and the remote host.

Text is limited to Telegram's 4,096 UTF-16 code units, or 1,024 for photo captions.
Most characters use one unit; emoji can use two.

The cooldown starts before sending and also applies to failed attempts, so a
burst of messages does not trigger repeated retries. Messages received during
the cooldown are skipped, not queued. Timing uses an in-memory monotonic clock
and resets when the process restarts. Run one instance per account/session.
When Telegram requests a flood wait, all replies pause for that interval;
messages received during the pause are skipped.

## Local checks

The tests use only the Python standard library. No credentials, dependency
installation, or Telegram connection are required:

```bash
python -m unittest discover -s tests -v
python -m py_compile settings.py tgbot.py
```

GitHub Actions runs these checks on Python 3.10 and 3.12 for pushes and pull requests.
