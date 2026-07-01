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

Morning live-entry research and trading flow:

1. At 7:00 AM America/Los_Angeles on weekdays, Codex starts the `Robinhood Agentic Morning Live Trade` automation locally.
2. The automation uses `gpt-5-codex` and the guardrails in the automation prompt.
3. It reads the configured Robinhood Agentic account`YOUR_LAST4` through Robinhood MCP.
4. It checks portfolio value, buying power, current positions, recent agentic orders, tradability, and quotes.
5. It researches current market context and symbol-specific news for the controlled expanded universe in the same model run that will make the trade decision.
6. Before any order review or placement, it writes a live-entry audit note to `data/research/YYYY-MM-DD-live-entry.md`.
7. The audit note includes timestamp, account snapshot, quote table, broad market read, symbol-by-symbol bull/bear notes, risk flags, source links, candidate ranking, skipped symbols, and the final trade/no-trade thesis.
8. It records the thesis, candidates, skipped symbols, and final decision into `data/trading_journal.sqlite`.
9. It runs local preflight:

```bash
env PYTHONPATH=src python -m agentic_trader.cli preflight --config config/default.json
```

The local Python CLI is intentionally dry-run-safe, so preflight may report `mode=dry-run`, `live_trading_enabled=false`, `i_understand_risk=false`, or `ready_for_live_orders=false`. Those are expected local-CLI safety signals and should not block the Codex MCP live automation by themselves. The live automation should block only on real operational problems such as a kill switch, malformed config, failed local paths, wrong strategy/account setup, or Robinhood MCP warnings.

10. It decides whether any long-only equity/ETF trade fits the strategy and guardrails.
11. For each candidate, it calls Robinhood `review_equity_order` first.
12. Only if the review is clean, it may call `place_equity_order`.
13. Afterward it reads portfolio/orders again, records order outcomes in the journal, and sends an email summary with trades, skipped candidates, reasons, risk checks, research links, and the audit note path.

Morning holdings review:

- Before choosing new buys, the live automation reviews current holdings and their original journaled thesis.
- It researches holding-specific news, catalysts, negative headlines, and benchmark context.
- It decides whether each holding should be held, trimmed, exited, or cautiously added to.
- Add-to-existing is allowed only when the original thesis is still valid, current research is supportive, exposure caps allow it, and the add is small.
- It should not average up or down mechanically. Any add must be thesis-driven and stay within the configured notional/exposure caps.

Intraday risk flow:

1. Every 30 minutes from 8:45 AM through 1:30 PM America/Los_Angeles on weekdays, Codex starts the `Robinhood Agentic Intraday Risk Monitor`.
2. This monitor does not open new positions.
3. It checks current positions and quotes through Robinhood MCP.
4. It reviews current holdings against their original thesis, holding-specific research, and account risk.
5. It may exit strategy positions if a 6% stop loss, 12% take profit, `$200` account drawdown condition, or clear thesis-invalidation condition is hit.
6. It must call `review_equity_order` before any sell order.
7. It records position/risk checks and exit decisions in `data/trading_journal.sqlite`.
8. It sends an email only when it exits or detects a meaningful risk condition.

Midday opportunity flow:

1. Around 10:30 AM America/Los_Angeles on weekdays, Codex starts the `Robinhood Agentic Midday Opportunity Scan`.
2. This is the only intraday automation that may open or add to a position.
3. It first reads the current account, current holdings, recent orders, same-day stops/exits, buying power, quote data, tradability, and recent journal events.
4. It uses Robinhood MCP read-only data wherever available, including quote/market data, portfolio/order data, tradability, and any additional MCP-provided fundamentals, analyst, ratings, news, or event data exposed by the connected tools.
5. It also performs fresh web/news research for current holdings and the controlled universe.
6. It may place at most one buy/add order, capped at `$75` total midday deployment and `$50` for adding to an existing position.
7. It may also trim or exit if fresh research or MCP data shows a severe adverse event, thesis invalidation, abnormal market behavior, or a hard risk trigger.
8. It must not re-enter the same symbol after a same-day stop-loss, and it should not enter the same exposure group after a stop-loss unless the new trade is clearly uncorrelated and risk-reducing.
9. If the account is red on the day, correlated intraday buys require an unusually strong, directly relevant setup; otherwise the scan should hold cash.
10. Every decision is recorded in `data/trading_journal.sqlite` and, when possible, summarized by email.

Weekly strategy review flow:

1. Every Friday at 2:00 PM America/Los_Angeles, Codex starts the `Robinhood Agentic Weekly Strategy Review`.
2. This automation is analysis-only.
3. It must not place trades.
4. It must not edit config files or automation prompts.
5. It reads Robinhood portfolio, orders, positions, and realized P/L through MCP.
6. It reads recent events from `data/trading_journal.sqlite`.
7. It reviews how the controlled expanded momentum strategy performed during the week.
8. It emails a strategy review with performance, risk, trade/order summary, open positions, research usefulness, and suggested changes.
9. Recommended changes require a human follow-up before they are applied.

## What Makes The Decisions

The live trade decision is made by the scheduled Codex agent using `gpt-5-codex`, constrained by:

- the automation prompt,
- the strategy/risk settings in [config/default.json](config/default.json),
- read-only account/quote/tradability data from Robinhood MCP,
- current research/news context,
- Robinhood pre-trade review results.

The model is allowed to choose no trade. Skipping is expected if research fails, quotes are stale, Robinhood returns warnings, spreads look abnormal, the market context is unclear, or the guardrails would be exceeded.

The model is not allowed to redesign or self-modify the strategy automatically. It can recommend changes in the weekly strategy review, but those changes should be applied only after you explicitly approve them.

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
- Daily live-entry research/thesis notes in `data/research/YYYY-MM-DD-live-entry.md`.
- Structured trading journal in `data/trading_journal.sqlite`.

Simulated/local:

- `run-once` uses the local dry-run execution client.
- `simulate` uses temporary local state.
- Local `state/portfolio.json` is not the source of truth for real positions; Robinhood is.
- Generated research/thesis notes are ignored by git unless intentionally copied into docs.
- The SQLite journal is ignored by git because it is runtime account/trading data.

Not currently supported for live trading in this setup:

- options,
- crypto,
- futures,
- short selling,
- multi-leg options,
- any account with `agentic_allowed=false`.

## Recommended Starting Strategy

For a `$650` account, start with `expanded_momentum_guarded`:

- Core leveraged ETF universe: `TQQQ`, `UPRO`, `SPXL`, `SOXL`
- Expanded ETF/ETN candidates: `TECL`, `FNGU`, `USD`, `BULZ`
- Single-stock candidates: `NVDA`, `AMD`, `MSFT`, `META`, `GOOGL`, `AMZN`, `TSLA`, `COIN`, `PLTR`
- Safe-mode candidates: `SGOV`, `BIL`, `SHV`
- Target position: `20%`
- Max allocation to one symbol: `30%`
- Max open positions: `3`
- Max new positions per day: `2`
- Max leveraged ETF/ETN entry: `$130`
- Max single-stock entry: `$90`
- Max intraday opportunity buy/add orders: `1`
- Max intraday opportunity deployed: `$75`
- Max intraday add to existing position: `$50`
- Max one single-stock entry at first
- Max one position per exposure group
- Max new deployed per morning: `$260`
- Max total strategy exposure: about `$390`
- Risk per trade: `3%` of equity
- Stop loss: `6%`
- Take profit: `12%`
- Daily bot shutdown: `$200`
- Weekly bot shutdown: `$300`

Your requested `$200` daily and `$300` weekly limits are very aggressive for a `$650` account. The system honors them, but v1 still uses smaller position sizing so one bad idea does not immediately consume the entire daily limit.

## Expanded Universe Rules

The current strategy researches a wider list but trades narrowly. The point is to avoid forcing a trade into `TQQQ`, `SOXL`, `UPRO`, or `SPXL` when another liquid, Robinhood-supported candidate has cleaner momentum and more relevant research.

Exposure groups:

- Nasdaq/growth: `TQQQ`, `TECL`, `FNGU`, `BULZ`
- S&P 500 broad market: `UPRO`, `SPXL`
- Semiconductors: `SOXL`, `USD`, `NVDA`, `AMD`
- Mega-cap growth: `MSFT`, `META`, `GOOGL`, `AMZN`, `TSLA`
- Crypto beta: `COIN`
- Speculative growth: `PLTR`
- Safe mode: `SGOV`, `BIL`, `SHV`

The morning live trade automation should usually place zero to two opening trades. It should not buy multiple symbols from the same exposure group in one morning, and it should not add a single-stock position unless the current research is directly relevant to that symbol. Safe-mode symbols are available when the market setup is weak and the best decision is capital preservation.

Existing holdings are researched separately from new candidates. The bot should be able to say why each current holding is still valid, invalidated, worth trimming, or worth a small add. For holdings, the default is not to churn. It should hold through normal noise, sell on hard risk triggers, and only trim/exit early when the original thesis is clearly broken or risk concentration becomes unacceptable.

The midday scan gives the bot more flexibility, but it is intentionally narrower than the morning run. It is allowed to buy only when current Robinhood MCP data, price action, account state, and fresh research line up. It is not allowed to replace a stopped-out semiconductor trade with another semiconductor trade just because the symbol is moving. After a stop-loss, the same symbol is blocked for the rest of the day, and the same exposure group should be avoided unless the trade is genuinely uncorrelated or reduces portfolio risk.

Research-driven intraday exits are allowed. Examples include a severe company-specific adverse event, a thesis-breaking regulatory/legal headline, an earnings or guidance shock, a trading halt/stale quote/rejection-risk path, or material benchmark underperformance after the original catalyst disappears. Ordinary volatility is not enough by itself.

## Strategy Profiles

`aggressive_momentum_news`
: Single-name momentum/news strategy for volatile large caps. Highest upside and highest gap risk.

`leveraged_etf_swing`
: Original v1. Uses four leveraged ETFs for aggressive exposure while avoiding single-company earnings blowups.

`expanded_momentum_guarded`
: Current profile. Scores a wider, Robinhood-tradable universe but only trades the best one or two candidates after research, quote checks, account checks, and exposure-group limits. This gives the agent more flexibility without letting it stack redundant risk.

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

## Trading Journal

The local journal stores the bot's operational memory:

```text
data/trading_journal.sqlite
```

It is a SQLite database with timestamped events such as:

- account snapshots
- research/thesis summaries
- candidate trades
- skipped trades
- Robinhood order reviews
- placed orders
- intraday risk checks
- exits
- weekly review recommendations

Initialize it manually:

```bash
env PYTHONPATH=src python -m agentic_trader.cli journal-init --config config/default.json
```

Record a manual event:

```bash
env PYTHONPATH=src python -m agentic_trader.cli journal-record --config config/default.json \
  --event-type note \
  --source manual \
  --payload-json '{"summary":"manual note"}'
```

Summarize recent events:

```bash
env PYTHONPATH=src python -m agentic_trader.cli journal-summary --config config/default.json --limit 20
```

The automations are instructed to write to this journal. It improves auditability and lets future strategy reviews compare the bot's original thesis against what happened later. Robinhood remains the source of truth for actual orders, positions, and P/L.

## Keep The Laptop Awake

The Codex automations run locally, so the laptop must stay awake and online during trading hours. To keep macOS awake, open a terminal and run:

```bash
caffeinate -dimsu
```

Leave that terminal window open while you want the automations to run. Stop it with `Ctrl-C` when you no longer need the laptop held awake.

## Kill Switch

Create this file to block new trades:

```text
state/KILL_SWITCH_ON
```

## Live Trading Gates

There are two separate execution paths:

- Local Python CLI: dry-run-safe by design. It should keep `live_trading_enabled=false` unless a real broker adapter is implemented later.
- Codex MCP automation: the current live path. It can place live trades directly through Robinhood MCP after account checks, research, audit logging, and `review_equity_order`.

Codex MCP live trading should remain disabled until all of these are true:

- The Robinhood MCP is connected in Codex.
- MCP tool support is verified for the intended instrument type.
- Portfolio/position reconciliation works.
- Dry-run logs show sane orders, exposure, P/L, and risk decisions.
- The live automation prompt explicitly authorizes autonomous trading and hard guardrails.
- The account is confirmed as `agentic_allowed=true`.

The current `RobinhoodMcpExecutionClient` intentionally raises an error until the live tool mapping is implemented.

## Current Automations

Codex has active local cron automations for the Agentic account.

- `Robinhood Agentic Morning Research Prep`
  - Status: paused
  - This was a separate research-only prep step, but it is paused because the optimized flow now does fresh research inside the 7:00 AM live-entry automation.

- `Robinhood Agentic Morning Live Trade`
  - Schedule: weekday mornings at 7:00 AM America/Los_Angeles
  - Model: `gpt-5-codex`
  - Mode: guarded live equities/ETF trading through Robinhood MCP
  - Account: configured Robinhood Agentic account`YOUR_LAST4`
  - Universe: `TQQQ`, `UPRO`, `SPXL`, `SOXL`, `TECL`, `FNGU`, `USD`, `BULZ`, `NVDA`, `AMD`, `MSFT`, `META`, `GOOGL`, `AMZN`, `TSLA`, `COIN`, `PLTR`, `SGOV`, `BIL`, `SHV`
  - It performs fresh research in the same model run that makes the trade decision.
  - It researches existing holdings and their original thesis before looking for new entries.
  - It writes a live-entry audit note to `data/research/YYYY-MM-DD-live-entry.md` before any order review or placement.
  - It records research, candidates, skipped trades, reviews, and order outcomes in `data/trading_journal.sqlite`.
  - Hard opening limits: max 2 new positions per morning, max `$130` per leveraged ETF/ETN, max `$90` per single stock, max `$260` new deployed per morning, max about `$390` total strategy exposure, keep roughly `$200` cash, no order under `$25`
  - Add-to-existing limits: only when thesis is reinforced, max `$60` add, and all exposure/cash caps remain satisfied.
  - Diversification limits: do not buy redundant proxies in the same exposure group, such as both `UPRO` and `SPXL`; at most one single-stock entry until more live history exists.
  - Single-stock entries require clearly relevant current research and must avoid known earnings-day entries unless explicitly approved.
  - It must call `review_equity_order` before any `place_equity_order`.
  - It must not call `place_option_order`.

- `Robinhood Agentic Midday Opportunity Scan`
  - Schedule: weekday late morning, around 10:30 AM America/Los_Angeles
  - Model: `gpt-5-codex`
  - Mode: guarded live equities/ETF opportunity scan through Robinhood MCP
  - It can buy/add at most once per run, with max `$75` total midday deployment and max `$50` add-to-existing.
  - It can also trim or exit when hard risk rules or severe research/data-driven thesis invalidation triggers.
  - It must read current holdings, current account value, same-day orders, same-day stop-losses, quotes, tradability, and recent journal events before deciding.
  - It should use all relevant read-only Robinhood MCP data exposed by the connected tools, plus fresh web/news research.
  - It must not re-enter the same symbol after a same-day stop-loss.
  - It must call `review_equity_order` before any `place_equity_order`.
  - It must not call `place_option_order`.

- `Robinhood Agentic Intraday Risk Monitor`
  - Schedule: every 30 minutes from 8:45 AM through 1:30 PM America/Los_Angeles on weekdays
  - Mode: exits/holds only, no new positions
  - Exit checks: 6% stop loss, 12% take profit, `$200` account drawdown from the `$650` reference, or clear thesis invalidation
  - It researches current holdings when there is a position-specific risk question, not just general market context.
  - It records position checks and exit decisions in `data/trading_journal.sqlite`.

- `Robinhood Agentic Weekly Strategy Review`
  - Schedule: Fridays at 2:00 PM America/Los_Angeles
  - Mode: analysis-only
  - It reviews weekly P/L, drawdown, orders, open positions, journal events, research usefulness, and suggested strategy changes.
  - It must not place trades or change strategy by itself.

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

The connected Agentic account currently supports this controlled expanded universe as tradable fractional equities/ETFs/ETNs:

```text
TQQQ, UPRO, SPXL, SOXL, TECL, FNGU, USD, BULZ, NVDA, AMD, MSFT, META, GOOGL, AMZN, TSLA, COIN, PLTR, SGOV, BIL, SHV
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
