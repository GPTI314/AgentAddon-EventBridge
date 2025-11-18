# AgentAddon-EventBridge

[![CI](https://github.com/GPTI314/AgentAddon-EventBridge/actions/workflows/ci.yml/badge.svg)](https://github.com/GPTI314/AgentAddon-EventBridge/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

Event bus + webhook ingestion + fanout microservice for AI/agent ecosystems

## Features

- **Hardening & Middleware**: Validation, correlation IDs, structured errors, unified logging
- **Pluggable Backends**: In-memory & Redis Streams adapters
- **Routing Rules Engine**: Flexible event matching and filtering
- **Authentication**: Optional API key authentication
- **WebSocket Streaming**: Real-time event delivery with rate limiting
- **Metrics & Telemetry**: Comprehensive observability

## Quick Start

```bash
pip install -r requirements.txt
python -m app.main
```

Visit http://localhost:8080/docs for API documentation.

## Development

```bash
make ci  # Run lint, typecheck, and tests with coverage
```

See [docs/adr/001-event-backend.md](docs/adr/001-event-backend.md) for architecture details.
