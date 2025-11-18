# EventBridge Extended Documentation

## Purpose
Portable event ingestion & routing layer, attachable to any agent system.

## Core Data Model
```json
{
  "id": "uuid",
  "source": "string",
  "type": "string",
  "payload": {"...": "..."},
  "correlation_id": "string|null",
  "ts": 1731900000.123
}
```

## Future Components
- Redis/Kafka backend abstraction.
- Subscription registry (target URL, auth headers, retry policy).
- Rule DSL example: `when type == 'task.complete' and payload.duration > 500 then notify 'perf-channel'`.

## Security Roadmap
- API key header `X-EB-Key`.
- Per-source rate limiting.
- Payload size guard.

## Suggested Claude Prompt Sequence
1. Design Redis stream integration & abstraction layer.
2. Implement subscriber registration persistence.
3. Add webhook dispatcher with exponential backoff.
4. Build rule engine with DSL parsing.
5. Integrate authentication + key rotation workflow.
6. Add metrics endpoint + Prometheus exposition.
7. Implement multi-tenant isolation (namespace parameter).
8. Add event replay endpoint with filters.
9. Harden validation + JSON schema enforcement.
10. Final performance profiling & optimization.
