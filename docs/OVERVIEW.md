# EventBridge Overview

EventBridge provides a minimal event ingestion layer decoupled from any core platform. It is intended to run as an addon container.

## Responsibilities
- Accept inbound events (source, type, payload) over REST
- Attach correlation IDs & timestamps
- Buffer events (in-memory now; extensible to Redis/Kafka)
- Offer recent query endpoint for lightweight consumption

## Extensibility Points
- Replace `EventBus` with pluggable backends
- Add auth middleware (API key / OAuth)
- Introduce filtering & subscription semantics
- Add WebSocket / SSE streaming layer

## Data Model (Current)
```
InboundEvent: { source, type, payload, correlation_id? }
StoredEvent: InboundEvent + { id, ts }
```

## Non-Goals (Initial)
- Long-term persistence
- Complex routing rules
- Multi-tenant isolation

## Future Enhancements
- Retry & dead-letter queue
- Event schema registry & validation
- Metrics emission (events/sec, lag, delivery counts)
