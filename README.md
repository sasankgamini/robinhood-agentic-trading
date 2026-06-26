# Robinhood Agentic Trading

Dry-run-first trading system for a dedicated high-risk Robinhood account. It is designed around a roughly `$650` account, autonomous operation after setup, and hard guardrails before any live trading path can run.

## Robinhood MCP Setup In Codex

Add the Robinhood Trading MCP server:

1. Open `Codex Settings`.
2. Go to `MCP servers`.
3. Choose `Streamable HTTP`.
4. Add:

```text
https://agent.robinhood.com/mcp/trading
```

After connecting, inspect the exposed MCP tools before enabling any live adapter. Current public reporting indicates Robinhood's agentic trading MCP starts with equities trading, while options, crypto, and futures are planned future additions. This repo therefore treats options and crypto as strategy interfaces only until the connected MCP proves support.

## How The Workflow Works

This setup has four moving parts:

- Codex automation: the scheduled agent runner on your laptop.
- `gpt-5-codex`: the model used by the scheduled Codex automation.
- Robinhood Trading MCP: the broker tool connection used for account reads, order reviews, and order placement.
- This Python repo: local config, dry-run simulation, preflight checks, research logging, state files, and email helper code.

The live workflow is agent-driven, not just a standalone Python bot. The Python CLI remains dry-run-safe by design; the Codex automation is the piece that can call Robinhood MCP live trading tools.

Morning live trading flow:

1. At 6:35 AM America/Los_Angeles on weekdays, Codex starts the `Robinhood Agentic Morning Live Trade` automation locally.
2. The automation uses `gpt-5-codex` and the guardrails in the automation prompt.
3. It reads the configured Robinhood Agentic account`YOUR_LAST4` through Robinhood MCP.
4. It checks portfolio value, buying power, current positions, recent agentic orders, tradability, and quotes.
5. It researches current market context and symbol-specific news for `TQQQ`, `SOXL`, `UPRO`, and `SPXL`.
6. It runs local preflight:

```bash
env PYTHONPATH=src python -m agentic_trader.cli preflight --config config/default.json
```

7. It decides whether any long-only leveraged ETF trade fits the strategy and guardrails.
8. For each candidate, it calls Robinhood `review_equity_order` first.
9. Only if the review is clean, it may call `place_equity_order`.
10. Afterward it reads portfolio/orders again and sends an email summary with trades, skipped candidates, reasons, risk checks, and research links.

Intraday risk flow:

1. Every 30 minutes from 7:00 AM through 1:30 PM America/Los_Angeles on weekdays, Codex starts the `Robinhood Agentic Intraday Risk Monitor`.
2. This monitor does not open new positions.
3. It checks current positions and quotes through Robinhood MCP.
4. It may exit strategy positions if a 6% stop loss, 12% take profit, or `$200` account drawdown condition is hit.
5. It must call `review_equity_order` before any sell order.
6. It sends an email only when it exits or detects a meaningful risk condition.

## What Makes The Decisions

The live trade decision is made by the scheduled Codex agent using `gpt-5-codex`, constrained by:

- the automation prompt,
- the strategy/risk settings in [config/default.json](config/default.json),
- read-only account/quote/tradability data from Robinhood MCP,
- current research/news context,
- Robinhood pre-trade review results.

The model is allowed to choose no trade. Skipping is expected if research fails, quotes are stale, Robinhood returns warnings, spreads look abnormal, the market context is unclear, or the guardrails would be exceeded.

This is best described as an agentic trading workflow:

```text
Codex scheduled automation
  -> gpt-5-codex reasoning
  -> local Python preflight/research helpers
  -> Robinhood MCP read tools
  -> Robinhood MCP order review
  -> Robinhood MCP order placement, only if review is clean
  -> email summary
```

## What Is Real vs Simulated

Real:

- Robinhood MCP account/portfolio/order/quote/tradability reads.
- Robinhood MCP order review.
- Robinhood MCP equity order placement from the live Codex automation.
- Email alerts through SMTP.
- RSS/news links when live research is enabled.

Simulated/local:

- `run-once` uses the local dry-run execution client.
- `simulate` uses temporary local state.
- Local `state/portfolio.json` is not the source of truth for real positions; Robinhood is.

Not currently supported for live trading in this setup:

- options,
- crypto,
- futures,
- short selling,
- multi-leg options,
- any account with `agentic_allowed=false`.

## Recommended Starting Strategy

For a `$650` account, start with `leveraged_etf_swing` in dry-run:

- Universe: `TQQQ`, `SOXL`, `UPRO`, `SPXL`
- Target position: `20%`
- Max allocation to one symbol: `30%`
- Max open positions: `3`
- Risk per trade: `3%` of equity
- Stop loss: `6%`
- Take profit: `12%`
- Daily bot shutdown: `$200`
- Weekly bot shutdown: `$300`

Your requested `$200` daily and `$300` weekly limits are very aggressive for a `$650` account. The system honors them, but v1 still uses smaller position sizing so one bad idea does not immediately consume the entire daily limit.

## Strategy Profiles

`aggressive_momentum_news`
: Single-name momentum/news strategy for volatile large caps. Highest upside and highest gap risk.

`leveraged_etf_swing`
: Recommended v1. Uses leveraged ETFs for aggressive exposure while avoiding single-company earnings blowups.

`options_speculation`
: Disabled for live use unless the Robinhood MCP exposes compliant options trading tools. Buying premium only; no short options.

`cash_preservation`
: Safe mode profile. Uses cash-like ETFs with tight limits.

## Run Dry-Run

```bash
env PYTHONPATH=src python -m agentic_trader.cli run-once --config config/default.json
```

State is written to `state/portfolio.json`; logs are written to `logs/trades.jsonl`.

If you want to clear simulated positions and start dry-run state from `$650` again:

```bash
env PYTHONPATH=src python -m agentic_trader.cli reset-state --config config/default.json
```

Use preflight before any scheduled run:

```bash
env PYTHONPATH=src python -m agentic_trader.cli preflight --config config/default.json
```

## Kill Switch

Create this file to block new trades:

```text
state/KILL_SWITCH_ON
```

## Live Trading Gates

Live trading must remain disabled until all of these are true:

- The Robinhood MCP is connected in Codex.
- MCP tool support is verified for the intended instrument type.
- Portfolio/position reconciliation works.
- Dry-run logs show sane orders, exposure, P/L, and risk decisions.
- `config/default.json` has both:

```json
"live_trading_enabled": true,
"i_understand_risk": true
```

The current `RobinhoodMcpExecutionClient` intentionally raises an error until the live tool mapping is implemented.

## Current Automations

Codex has active local cron automations for the Agentic account.

- `Robinhood Agentic Morning Live Trade`
  - Schedule: weekday mornings at 6:35 AM America/Los_Angeles
  - Model: `gpt-5-codex`
  - Mode: guarded live equities/ETF trading through Robinhood MCP
  - Account: configured Robinhood Agentic account`YOUR_LAST4`
  - Universe: `TQQQ`, `SOXL`, `UPRO`, `SPXL`
  - Hard opening limits: max 3 symbols, max `$130` per symbol, max `$390` total deployed, keep roughly `$200` cash, no order under `$25`
  - It must call `review_equity_order` before any `place_equity_order`.
  - It must not call `place_option_order`.

- `Robinhood Agentic Intraday Risk Monitor`
  - Schedule: every 30 minutes from 7:00 AM through 1:30 PM America/Los_Angeles on weekdays
  - Mode: exits only, no new positions
  - Exit checks: 6% stop loss, 12% take profit, or `$200` account drawdown from the `$650` reference

The local Python CLI remains dry-run-safe. Live trading is currently performed only by the Codex automation using Robinhood MCP tools.

Previous dry-run-only behavior:

- Schedule: weekday mornings at 6:20 AM America/Los_Angeles
- Model: `gpt-5-codex`
- Mode: dry-run and read-only Robinhood MCP checks
- Account: configured Robinhood Agentic account`YOUR_LAST4`
- It may call read-only tools such as account, portfolio, positions, orders, tradability, and quotes.
- It must not call `place_equity_order` or `place_option_order`.

That dry-run automation has been replaced by the guarded live workflow above.

## Current Robinhood Account Status

The connected Agentic account currently supports this v1 universe as tradable equities/ETFs:

```text
TQQQ, SOXL, UPRO, SPXL
```

Options are not enabled on the Agentic account at the moment, even though another non-agentic account has options level 2. The bot therefore treats options as unavailable for live trading.

## Deployment Tradeoffs

`Codex local only`
: Best for build/test and manual supervised dry-runs. Not reliable for always-on automation.

`Always-on laptop`
: Most practical early live option if MCP auth depends on local Codex/browser session. Weaknesses: sleep, Wi-Fi, OS updates, and local secret hygiene.

`GitHub Actions scheduled jobs`
: Free and simple for periodic scans, but poor for secrets, long-running state, and MCP auth unless Robinhood supports non-interactive remote auth. Latency is also unpredictable.

`Cloudflare Workers / cron`
: Good free cron and logs, but MCP auth and Python runtime fit may be awkward. Better for a stateless signal checker than broker execution.

`Small paid VPS`
: Best reliability once live trading is real: stable runtime, process supervisor, logs, encrypted secrets, scheduled jobs. Usually worth the small cost if autonomous execution matters.

## Research Layer

The current build uses deterministic fixtures so tests and default dry-runs are repeatable. It also includes an optional RSS research provider behind `research.enable_live_news`.

Future research providers should be added through explicit APIs or permitted feeds:

- market/news API or RSS provider
- earnings calendar provider
- analyst/news sentiment scorer
- social sentiment only through compliant APIs or permitted public feeds

No unofficial Robinhood scraping should be used.
