# 📋 Changelog

## v1.0.0 — 2026-10-12

First versioned release of Telegram Auto-Reply.

- ⚙️ Configure credentials, reply text, optional media and cooldown through `.env`.
- 🛡️ Validate settings before connecting and keep credentials and session files out of Git.
- 💬 Send plain text, fall back to text if photo delivery fails, and optionally follow with a GIF.
- ⏱️ Reserve a sender during delivery so slow requests cannot trigger overlapping replies.
- 🚦 Handle every Telegram flood wait with a shared pause, including short waits.
- 🧪 Add 20 offline tests covering configuration, delivery, cooldown and failure paths.
- 📄 Include the MIT license and documented setup for Python 3.10 or newer.

### Validation

All 20 offline tests and syntax checks passed on Python 3.12. The dependency
audit found no known vulnerabilities on 2026-10-11. GitHub Actions checks
Python 3.10 and 3.12. Actual account login and delivery to Telegram were not
tested locally.

### Updating

Install dependencies with `python -m pip install -r req.txt`, set credentials
in your own `.env`, and run one instance per account/session. Cooldowns and
flood pauses are stored in memory and reset when the process restarts.
