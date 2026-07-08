# Architecture

Atlas Trade Engine is organized in five independent layers. Each layer
only depends on the abstractions below it, so any single layer (the
broker, the strategy, or the risk rules) can be replaced without
touching the others.

```
┌─────────────────────────────────────────────────────────────────┐
│                            main.py (CLI)                        │
└───────────────────────────────┬─────────────────────────────────┘
                                 │ builds and wires
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                     engine.py (TradingEngine)                    │
│  connects broker → streams bars → strategy → risk → execution   │
│  owns reconnect / safe-shutdown lifecycle                       │
└──────┬───────────────┬───────────────┬──────────────┬───────────┘
       │               │               │              │
       ▼               ▼               ▼              ▼
┌────────────┐  ┌───────────────┐ ┌───────────┐ ┌───────────────┐
│  brokers/  │  │  strategy/    │ │  risk/    │ │  execution/   │
│  base.py   │  │  base_strategy│ │  risk_    │ │  order_       │
│  (ABC)     │  │  .py (ABC)    │ │  manager  │ │  manager.py   │
│            │  │               │ │  .py      │ │               │
│ Alpaca /   │  │ Momentum      │ │ Sizing,   │ │ Retries,      │
│ Paper impl │  │ example       │ │ stops,    │ │ idempotent    │
│            │  │ (replace with │ │ slippage, │ │ order IDs,    │
│            │  │ your rules)   │ │ daily     │ │ audit logging │
│            │  │               │ │ loss cap  │ │               │
└────────────┘  └───────────────┘ └───────────┘ └───────────────┘
```

## Data flow, one bar at a time

1. `BrokerClient.stream_bars()` yields a `Bar`.
2. `TradingEngine` appends it to a rolling in-memory window and checks
   the daily loss circuit breaker.
3. `BaseStrategy.generate_signal()` turns the window into a `Signal`
   (`LONG`, `SHORT`, or `HOLD`).
4. On a non-`HOLD` signal, `RiskManager` computes position size from
   account equity and the configured stop distance, and validates the
   proposed fill against the slippage buffer.
5. `OrderManager` submits the order with automatic retries and an
   idempotent client order ID, and logs the fill for auditing.

## Reconnection and safe shutdown

- The Alpaca adapter's `stream_bars()` runs its own reconnect loop
  with exponential backoff (`RECONNECT_BASE_DELAY` →
  `RECONNECT_MAX_DELAY`), and backfills any bars missed while
  disconnected via the REST API before resuming the stream.
- On `SIGINT`/`SIGTERM`, `TradingEngine` stops consuming new bars and,
  if `FLATTEN_ON_SHUTDOWN=true`, sends market orders to close every
  open position before disconnecting -- so the bot never leaves a
  position open because the process was killed.

## Swapping in your own strategy

Implement `BaseStrategy` with your own entry/exit rules:

```python
from atlas_trader.strategy.base_strategy import BaseStrategy
from atlas_trader.models import Signal

class MyStrategy(BaseStrategy):
    @property
    def warmup_bars(self) -> int:
        return 50

    def generate_signal(self, bars) -> Signal:
        # your indicators and rules here
        ...
```

Then point `main.py` at it instead of `MomentumStrategy`. Nothing else
in the engine needs to change.

## Swapping in a different broker

Implement `BrokerClient` (see `alpaca_broker.py` for a full reference)
for Interactive Brokers, Binance via `ccxt`, or any other REST/
WebSocket API, and pass it into `TradingEngine` the same way.
