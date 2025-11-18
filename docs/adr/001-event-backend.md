# ADR 001: Event Backend Storage Strategy

**Status**: Proposed
**Date**: 2025-11-18
**Decision Makers**: Engineering Team
**Tags**: persistence, architecture, scalability

## Context

AgentAddon EventBridge currently uses an in-memory event storage backend (`InMemoryAdapter`). While this is sufficient for development and testing, production deployments require durable, scalable event storage. We need to evaluate persistent backend options that can support:

- Event durability (survive service restarts)
- High throughput (thousands of events per second)
- Event replay capabilities
- Multi-consumer patterns
- Horizontal scalability
- Query capabilities for event history

## Decision Drivers

1. **Durability**: Events must not be lost on service failure
2. **Performance**: Minimal latency impact on event publishing
3. **Scalability**: Support for growing event volumes
4. **Query Patterns**: Support for recent event listing, filtering, and replay
5. **Operational Complexity**: Ease of deployment and maintenance
6. **Cost**: Infrastructure and operational costs

## Options Considered

### Option 1: Redis Streams

**Description**: Use Redis Streams as the event storage backend (already implemented as `RedisStreamAdapter`).

**Pros**:
- Low latency (~1-2ms publish latency)
- Built-in support for consumer groups
- Simple deployment and operations
- Good for real-time event streaming
- Already partially implemented
- Automatic trimming with `MAXLEN`

**Cons**:
- Limited durability guarantees (in-memory with optional persistence)
- Not designed for long-term event storage
- Limited query capabilities compared to databases
- Single-point-of-failure without Redis Cluster
- Memory-bound storage capacity

**Best For**: Real-time event streaming with short retention periods (hours to days)

**Estimated Throughput**: 50K-100K events/second per Redis instance

---

### Option 2: Apache Kafka

**Description**: Use Kafka as a distributed event streaming platform.

**Pros**:
- Industry-standard for event streaming
- Excellent durability with replication
- Horizontal scalability
- Long-term event retention
- Strong consumer group support
- High throughput
- Event replay capabilities

**Cons**:
- Higher operational complexity (requires Zookeeper/KRaft)
- Increased infrastructure costs
- Higher latency than Redis (~5-10ms)
- Steeper learning curve
- Overkill for simple use cases

**Best For**: Large-scale production systems requiring long-term event retention and strong durability

**Estimated Throughput**: 1M+ events/second across cluster

---

### Option 3: PostgreSQL with LISTEN/NOTIFY

**Description**: Store events in PostgreSQL tables with optional LISTEN/NOTIFY for real-time updates.

**Pros**:
- Strong durability and ACID guarantees
- Rich query capabilities (SQL)
- Familiar tooling and operations
- Good for event sourcing patterns
- JSON/JSONB support for flexible payloads
- Integrated with existing database infrastructure

**Cons**:
- Higher write latency (~10-50ms depending on configuration)
- LISTEN/NOTIFY not designed for high-throughput streaming
- Requires careful index management for performance
- Scaling writes requires partitioning/sharding

**Best For**: Applications prioritizing durability, query flexibility, and integration with existing PostgreSQL infrastructure

**Estimated Throughput**: 10K-50K events/second per instance (with proper tuning)

---

### Option 4: MongoDB with Change Streams

**Description**: Store events in MongoDB with Change Streams for real-time notifications.

**Pros**:
- Document model fits event structure naturally
- Good query flexibility
- Change Streams for real-time updates
- Horizontal scalability through sharding
- Good performance for reads and writes

**Cons**:
- Eventual consistency in sharded deployments
- Change Streams require replica sets
- Higher operational complexity than single-node databases
- Not specifically designed for event streaming

**Best For**: Applications requiring flexible document storage with real-time change notifications

**Estimated Throughput**: 50K-100K events/second across cluster

---

### Option 5: Hybrid Approach (Redis + PostgreSQL)

**Description**: Use Redis Streams for real-time event streaming and PostgreSQL for durable long-term storage.

**Pros**:
- Best of both worlds: low latency + durability
- Redis for hot data, PostgreSQL for cold data
- Flexible retention policies
- SQL query capabilities for historical analysis

**Cons**:
- Increased complexity (two systems to manage)
- Data synchronization challenges
- Higher infrastructure costs
- Potential for data consistency issues

**Best For**: Production systems requiring both real-time streaming and long-term durable storage

---

## Comparison Matrix

| Criteria | Redis Streams | Kafka | PostgreSQL | MongoDB | Hybrid |
|----------|---------------|-------|------------|---------|--------|
| Durability | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Latency | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| Throughput | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Query Flexibility | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Operational Simplicity | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ |
| Cost | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ |
| Scalability | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |

## Decision

**Initial Implementation**: Continue with **Redis Streams** (already implemented) for MVP and early production.

**Migration Path**:
1. **Phase 1** (Current): Redis Streams for development and small-scale production
2. **Phase 2** (3-6 months): Evaluate Hybrid (Redis + PostgreSQL) based on usage patterns
3. **Phase 3** (6-12 months): Migrate to Kafka if event volumes exceed 100K events/second

**Rationale**:
- Redis Streams provides good balance of performance and simplicity for initial deployments
- Pluggable adapter pattern allows seamless migration to other backends
- Defer complex infrastructure until usage patterns justify the complexity
- PostgreSQL can be added later for durable archival without replacing Redis

## Implementation Notes

### Current Architecture

The `BusAdapter` interface allows swapping backends without changing application code:

```python
# app/adapters/base.py
class BusAdapter(ABC):
    @abstractmethod
    async def publish(self, evt: InboundEvent) -> StoredEvent:
        pass

    @abstractmethod
    async def list_recent(self, limit: int = 50) -> Iterable[StoredEvent]:
        pass
```

### Adding New Backends

To add a new backend (e.g., Kafka):

1. Create `app/adapters/kafka.py` implementing `BusAdapter`
2. Add configuration option: `BUS_ADAPTER: Literal["memory", "redis", "kafka"]`
3. Update `_create_default_adapter()` in `app/services/event_bus.py`
4. Add integration tests

### TODO: Future Persistence Enhancements

- [ ] Implement KafkaAdapter with `aiokafka`
- [ ] Implement PostgresAdapter with `asyncpg`
- [ ] Add event archival service (Redis → PostgreSQL)
- [ ] Implement event replay API
- [ ] Add configurable retention policies
- [ ] Support event partitioning by source/type
- [ ] Add backup/restore functionality
- [ ] Implement dead letter queue for failed events

## Consequences

### Positive
- Clean abstraction allows easy migration
- Low operational overhead initially
- Fast time-to-market
- Good performance for expected workloads

### Negative
- Redis Streams durability limitations require careful configuration
- May need migration if durability requirements increase
- Limited historical query capabilities

### Neutral
- Team needs to monitor event volumes and retention requirements
- Decision should be revisited in 6 months based on production metrics

## References

- [Redis Streams Documentation](https://redis.io/docs/data-types/streams/)
- [Apache Kafka Documentation](https://kafka.apache.org/documentation/)
- [PostgreSQL LISTEN/NOTIFY](https://www.postgresql.org/docs/current/sql-notify.html)
- [MongoDB Change Streams](https://www.mongodb.com/docs/manual/changeStreams/)

---

**Next Review Date**: 2026-05-18
**Success Metrics**:
- Event loss rate < 0.01%
- P99 publish latency < 50ms
- Support 10K events/second sustained
