# Contributing

Thanks for considering a contribution to Atlas Trade Engine.

## Development setup

```bash
git clone https://github.com/MrBoyard7/atlas-trade-engine.git
cd atlas-trade-engine
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

## Before opening a pull request

```bash
black src tests
ruff check src tests
PYTHONPATH=src pytest --cov=src/atlas_trader
```

All three must pass locally; the same checks run in CI on every push
and pull request.

## Guidelines

- Keep broker, strategy, risk, and execution concerns in their own
  modules -- see `docs/architecture.md`.
- New strategies should implement `BaseStrategy` and ship with unit
  tests using synthetic OHLCV data.
- New broker adapters should implement `BrokerClient` and must never
  read or write credentials outside of environment variables.
- Write tests against the `PaperBroker` simulator rather than a live
  broker connection.

## Reporting issues

Please open a GitHub issue with steps to reproduce, the expected
behavior, and relevant log excerpts (with any account identifiers
redacted).
