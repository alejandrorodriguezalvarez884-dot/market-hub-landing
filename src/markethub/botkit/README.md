# Your Market Hub bot

This folder builds your bot for the **bot competition** of Market Hub
(My Hub > Community > Bot competition): a set of rules that picks US stocks, run on paper by
Market Hub and ranked against the other members' bots. No money and no broker are involved.

## How to use it

1. **Unzip this folder** wherever you like.
2. **Check `.env`.** If you downloaded the kit from the Bot competition page, your key is already
   in it. If not, press "New key" on that page and paste it after `MARKETHUB_BOT_KEY=` (copy
   `.env.example` to `.env` first). Keep the key to yourself: anyone with it can send in a bot for you.
3. **Open the folder with your AI agent** and say "Let's build my bot":
   - Claude Code: `cd` into the folder and run `claude` (or open it in the Claude app's Code tab).
   - Codex: `codex` in the folder.
   - Any other agent: point it at `AGENTS.md`.
4. It asks about your idea (or proposes some), writes `bot.json`, checks it, backtests it and,
   when you say so, sends it in. Then it shows up on the board from the next market close.

## What is inside

- `AGENTS.md`: what your agent does, step by step (`CLAUDE.md` and `GEMINI.md` point to it).
- `SPEC.md`: the format of a bot, how it is run and measured, and the API.
- `examples/`: bots that work, to start from.
- `tools/mh.py`: check, backtest, send in and follow your bot (Python 3.9+, nothing to install).
- `.claude/skills/build-bot/`: the same workflow as a Claude Code skill (`/build-bot`).

A new key from the page makes the old one stop working. Taking the key back from the page, or
deleting your Market Hub account, stops it too; deleting the account also deletes your bot.
