# Changelog

All notable changes to this project are documented in this file.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.1.0] - 2026-07-07

### Added
- Initial release: modular engine (broker / strategy / risk / execution layers).
- `PaperBroker` in-memory simulator for local development and CI.
- `AlpacaBroker` adapter with REST + WebSocket streaming, exponential
  backoff reconnection, and REST-based backfill after a dropped stream.
- Example `MomentumStrategy` (EMA crossover + RSI filter) as a
  reference implementation.
- `RiskManager` with position sizing, stop-loss/take-profit distances,
  a slippage guard, and a daily loss circuit breaker.
- `OrderManager` with retries, idempotent client order IDs, and full
  audit logging.
- Safe-shutdown flow that flattens open positions on `SIGINT`/`SIGTERM`.
- Docker + docker-compose one-command deployment.
- GitHub Actions CI (lint, format check, tests, coverage upload).
- Vectorized backtest script and sample OHLCV data.
