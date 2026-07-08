# Atlas Trade Engine

Autonomous, risk-managed algorithmic trading bot with a pluggable
strategy layer, a resilient broker adapter (REST + WebSocket, with
automatic reconnection), and Docker-ready deployment.

[![CI](https://github.com/MrBoyard7/atlas-trade-engine/actions/workflows/ci.yml/badge.svg)](https://github.com/MrBoyard7/atlas-trade-engine/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/MrBoyard7/atlas-trade-engine/branch/main/graph/badge.svg)](https://codecov.io/gh/MrBoyard7/atlas-trade-engine)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED.svg?logo=docker&logoColor=white)](docker/Dockerfile)

> **Risk disclaimer.** Automated trading involves substantial risk of
> loss and is not suitable for every investor. This project is
> provided for educational purposes and ships with a paper-trading
> simulator by default. Nothing in this repository is financial
> advice. Test thoroughly in a broker sandbox before ever connecting
> a live account, and never risk money you cannot afford to lose.

---

## Table of contents

- [Features](#features)
- [Architecture](#architecture)
- [Project structure](#project-structure)
- [Quick start](#quick-start)
- [Configuration](#configuration)
- [Running the tests](#running-the-tests)
- [Backtesting](#backtesting)
- [Docker deployment](#docker-deployment)
- [Deploying on AWS or DigitalOcean](#deploying-on-aws-or-digitalocean)
- [Extending with your own strategy](#extending-with-your-own-strategy)
- [Contributing](#contributing)
- [License](#license)

## Features

- **Pluggable strategy layer** -- ships with an example EMA/RSI
  momentum strategy; swap in your own entry/exit rules without
  touching the engine, risk, or execution code.
- **Hard-coded risk management** -- position sizing from account
  equity, stop-loss/take-profit distances, a slippage buffer, and a
  daily loss circuit breaker that halts trading for the session.
- **Resilient market data** -- the Alpaca adapter reconnects with
  exponential backoff on a dropped WebSocket and backfills missed bars
  via REST, so the strategy never silently skips data.
- **Safe shutdown** -- on `SIGINT`/`SIGTERM` the engine can flatten
  every open position before disconnecting.
- **Full audit trail** -- every signal, order, fill, and error is
  logged to rotating log files, with a dedicated `trades.log` for
  execution auditing.
- **Paper trading by default** -- an in-memory broker simulator lets
  the whole system run end-to-end with zero credentials and zero
  financial risk.
- **Docker-ready** -- one command to build and run on any VPS (AWS,
  DigitalOcean, etc.).

## Architecture

```
BrokerClient (ABC) ──> TradingEngine ──> BaseStrategy (ABC)
       │                    │                   │
  Alpaca / Paper       RiskManager         Momentum example
                             │
                       OrderManager
```

See [`docs/architecture.md`](docs/architecture.md) for the full data
flow, the reconnect/safe-shutdown lifecycle, and how to swap in your
own strategy or broker.

## Project structure

```
atlas-trade-engine/
├── .github/
│   └── workflows/
│       └── ci.yml
├── docker/
│   └── Dockerfile
├── docs/
│   └── architecture.md
├── examples/
│   └── sample_ohlcv.csv
├── scripts/
│   └── run_backtest.py
├── src/
│   └── atlas_trader/
│       ├── __init__.py
│       ├── config.py
│       ├── engine.py
│       ├── logger.py
│       ├── main.py
│       ├── models.py
│       ├── brokers/
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── alpaca_broker.py
│       │   └── paper_broker.py
│       ├── data/
│       │   ├── __init__.py
│       │   └── market_data_feed.py
│       ├── strategy/
│       │   ├── __init__.py
│       │   ├── base_strategy.py
│       │   ├── indicators.py
│       │   └── momentum_strategy.py
│       ├── risk/
│       │   ├── __init__.py
│       │   └── risk_manager.py
│       └── execution/
│           ├── __init__.py
│           └── order_manager.py
├── tests/
│   ├── __init__.py
│   ├── test_engine.py
│   ├── test_order_manager.py
│   ├── test_risk_manager.py
│   └── test_strategy.py
├── .codecov.yml
├── .env.example
├── .gitignore
├── CHANGELOG.md
├── CONTRIBUTING.md
├── docker-compose.yml
├── LICENSE
├── pyproject.toml
├── README.md
├── requirements-dev.txt
└── requirements.txt
```

## Quick start

Requires Python 3.9+.

**Linux / macOS (bash/zsh):**

```bash
git clone https://github.com/MrBoyard7/atlas-trade-engine.git
cd atlas-trade-engine

python -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env

# Runs against the built-in paper-trading simulator -- no credentials needed.
PYTHONPATH=src python -m atlas_trader.main --mode paper
```

**Windows (PowerShell):**

```powershell
git clone https://github.com/MrBoyard7/atlas-trade-engine.git
cd atlas-trade-engine

python -m venv .venv
.venv\Scripts\Activate.ps1

pip install -r requirements.txt
Copy-Item .env.example .env

# Runs against the built-in paper-trading simulator -- no credentials needed.
$env:PYTHONPATH = "src"
python -m atlas_trader.main --mode paper
```

> PowerShell does not support the `VAR=value command` inline syntax used
> in bash. Set `$env:PYTHONPATH = "src"` once per terminal session, then
> every following command (tests, backtest, etc.) picks it up
> automatically until you close that window.

Stop it any time with `Ctrl+C`; the engine will flatten any simulated
open position and shut down cleanly.

To connect a real broker, set `BROKER_API_KEY` / `BROKER_API_SECRET`
in `.env` (Alpaca paper or live keys) and run with `--mode live`.
**Always start with Alpaca's own paper-trading endpoint
(`https://paper-api.alpaca.markets`, the `.env.example` default)
before ever pointing this at a live account.**

## Configuration

All parameters are environment variables (see `.env.example`) -- no
code changes required to tune the bot.

| Variable | Default | Description |
|---|---|---|
| `MODE` | `paper` | `paper` (simulator) or `live` (real broker) |
| `SYMBOL` | `AAPL` | Instrument to trade |
| `TIMEFRAME` | `1Min` | Bar timeframe |
| `FAST_MA_PERIOD` / `SLOW_MA_PERIOD` | `9` / `21` | EMA periods for the example strategy |
| `RSI_PERIOD`, `RSI_OVERBOUGHT`, `RSI_OVERSOLD` | `14`, `70`, `30` | RSI filter for the example strategy |
| `MAX_RISK_PER_TRADE_PCT` | `1.0` | % of equity risked per trade |
| `STOP_LOSS_PCT` / `TAKE_PROFIT_PCT` | `0.5` / `1.0` | Stop distance as % of entry price |
| `MAX_SLIPPAGE_PCT` | `0.1` | Max allowed deviation between expected and quoted fill price |
| `MAX_POSITION_PCT` | `20.0` | Max % of equity in a single position |
| `MAX_DAILY_LOSS_PCT` | `3.0` | Session drawdown that halts trading |
| `FLATTEN_ON_SHUTDOWN` | `true` | Close open positions on `SIGINT`/`SIGTERM` |
| `RECONNECT_BASE_DELAY` / `RECONNECT_MAX_DELAY` | `1.0` / `60.0` | Exponential backoff bounds for the market data stream |

## Running the tests

```bash
pip install -r requirements-dev.txt
PYTHONPATH=src pytest --cov=src/atlas_trader --cov-report=term-missing
```

**Windows (PowerShell):**

```powershell
pip install -r requirements-dev.txt
$env:PYTHONPATH = "src"
pytest --cov=src/atlas_trader --cov-report=term-missing
```

Format and lint checks (the same ones enforced in CI):

```bash
black --check src tests
ruff check src tests
```

Test suite coverage:

- `tests/test_risk_manager.py` -- position sizing, stop distances, the
  slippage guard, and the daily loss circuit breaker.
- `tests/test_strategy.py` -- indicator math and the example
  strategy's crossover detection.
- `tests/test_order_manager.py` -- retry-then-succeed and
  exhausted-retries behavior, using a monkeypatched broker to simulate
  a dropped connection.
- `tests/test_engine.py` -- end-to-end bar handling that opens a
  position on a real signal, and the safe-shutdown flow that flattens
  it.

## Backtesting

A minimal vectorized backtest runner is included, along with a
synthetic sample dataset:

```bash
PYTHONPATH=src python scripts/run_backtest.py examples/sample_ohlcv.csv
```

**Windows (PowerShell):**

```powershell
$env:PYTHONPATH = "src"
python scripts/run_backtest.py examples/sample_ohlcv.csv
```

Swap in your own historical OHLCV CSV (columns: `timestamp, open,
high, low, close, volume`) to backtest the example strategy, or edit
the script to import your own `BaseStrategy` implementation.

## Docker deployment

```bash
docker compose build
docker compose up -d
docker compose logs -f
```

This builds the image, starts the bot in `paper` mode by default
(edit `docker-compose.yml` or `.env` to switch to `live`), and mounts
`./logs` on the host so the audit trail survives container restarts.

To run the container directly instead of via Compose:

```bash
docker build -t atlas-trade-engine -f docker/Dockerfile .
docker run --rm --env-file .env -v "$(pwd)/logs:/app/logs" atlas-trade-engine --mode paper
```

## Deploying on AWS or DigitalOcean

1. Provision a small VM (e.g. an EC2 `t3.micro` or a DigitalOcean
   Droplet) with Docker installed.
2. Copy the repository and your **real** `.env` (never commit it) to
   the server.
3. Run `docker compose up -d --build`.
4. Point your process supervisor of choice (systemd, Docker's own
   `restart: unless-stopped`, or a process manager) at the container
   so it survives reboots.
5. Ship `./logs` to persistent storage or a log aggregator (e.g. via a
   mounted volume or a sidecar shipper) for long-term auditing.

## Extending with your own strategy

```python
from atlas_trader.strategy.base_strategy import BaseStrategy
from atlas_trader.models import Signal

class MyStrategy(BaseStrategy):
    @property
    def warmup_bars(self) -> int:
        return 50

    def generate_signal(self, bars) -> Signal:
        # your indicators and entry/exit rules here
        ...
```

Then point `main.py` at `MyStrategy` instead of `MomentumStrategy`.
Risk management, execution, reconnection, and safe shutdown do not
need to change.

## Contributing

Contributions are welcome -- see [`CONTRIBUTING.md`](CONTRIBUTING.md)
for the development setup and pre-PR checklist.

## License

Distributed under the MIT License. See [`LICENSE`](LICENSE) for the
full text.

Copyright (c) 2026 Prince Boyard MBOUNGOU NGOMA
