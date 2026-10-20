---
name: build-bot
description: Build, backtest and send in a bot for the Market Hub bot competition - interview the member about their idea (or propose some), write bot.json in the markethub-bot/1 format, check it and backtest it against the API, and send it in when they say so. Use when the member wants to make, change, test or submit their bot, or asks how theirs is doing.
---

# Build a bot for Market Hub

Follow [AGENTS.md](../../../AGENTS.md) step by step: it is the whole workflow and its rules.
[SPEC.md](../../../SPEC.md) is the format and the API; [examples/](../../../examples/) are valid bots
to start from. The helper is `tools/mh.py` (`check`, `backtest`, `submit`, `status`, `spec`).

In short:

1. Say what this is in three lines, and run `python tools/mh.py status` to check the key.
2. Ask for their idea, or propose three or four in plain words. Ask how many stocks, how often it
   trades and whether it steps aside in falling markets.
3. Write `bot.json` from the closest example; `check` it until it passes; show the `rules`.
4. `backtest --years 3`; explain it against SPY, with its notes (simulated past, today's largest
   companies, nothing about the future). Warn against tuning it too much to the past.
5. Sum up and ask before sending: it replaces any bot they had. Then `submit`.

Paper only, ideas not advice, and the key never leaves `.env`.
