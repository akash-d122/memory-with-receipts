# ruff: noqa: E501
"""Prometheus DB Alert Simulation and Ingestion Script
===================================================
Simulates realistic database operational alerts in Markdown format, then
ingests them into the Postgres RAG database.

Usage:
    uv run --env-file .env scripts/simulate_alerts.py
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from memory_with_receipts.core.config import Settings
from memory_with_receipts.db.base import Base
from memory_with_receipts.embeddings.gemini import GeminiEmbeddingProvider
from memory_with_receipts.embeddings.local import LocalEmbeddingProvider
from memory_with_receipts.ingestion.chunking.structure_aware import StructureAwareChunker
from memory_with_receipts.ingestion.parsers.markdown_parser import MarkdownParser
from memory_with_receipts.ingestion.parsers.text_parser import TextParser
from memory_with_receipts.ingestion.pipeline import IngestionPipeline

# Define the simulated alerts in Markdown format
SIMULATED_ALERTS = [
    (
        "Prometheus Alert: PostgreSQLReplicationLagCritical",
        """# Prometheus Alert: PostgreSQLReplicationLagCritical

## Alert Information
- **Alert Name**: PostgreSQLReplicationLagCritical
- **Severity**: critical
- **Instance**: db-replica-01.prod.internal:5432
- **Database**: production_db
- **Timestamp**: 2026-06-15T15:45:00Z
- **Status**: firing
- **Source**: Prometheus Alertmanager

## Alert Summary
PostgreSQL replication lag on replica instance db-replica-01 is extremely high (12.4 GB). This exceeds the critical alert threshold of 10 GB.

## Diagnostic Data / Metrics
- `pg_replication_lag_bytes`: 13,314,398,208 bytes (12.4 GB)
- Active Replication Slots: 2 active, 1 inactive (`inactive_logical_slot_01`)
- Disk Write Throughput on Primary: 180 MB/s (heavy bulk write detected)
- WAL Generation Rate: 220 MB/s

## Live Context & Error Logs
```text
2026-06-15 15:44:30.124 UTC [412] LOG:  started streaming WAL from primary at 1A/F0000000
2026-06-15 15:44:35.882 UTC [412] WARNING:  replication connection lost, retrying...
2026-06-15 15:44:40.912 UTC [412] ERROR:  could not receive data from WAL stream: rate limited by network bandwidth
```

## Recommended Runbook Reference
Please reference the **PostgreSQL: Inactive Logical Replication Slot** runbook or **RDS: Replication Lag Critical** runbook for active remediation steps.
""",
        "postgresql,replication,lag,alert,prometheus,live"
    ),
    (
        "Prometheus Alert: PostgreSQLMaxConnectionsReached",
        """# Prometheus Alert: PostgreSQLMaxConnectionsReached

## Alert Information
- **Alert Name**: PostgreSQLMaxConnectionsReached
- **Severity**: critical
- **Instance**: db-primary.prod.internal:5432
- **Database**: production_db
- **Timestamp**: 2026-06-15T16:00:00Z
- **Status**: firing
- **Source**: Prometheus Alertmanager

## Alert Summary
The number of active client connections has reached 96% of the configured maximum connections (480 active connections out of 500 max).

## Diagnostic Data / Metrics
- `pg_stat_activity_connections_active`: 480
- `pg_settings_max_connections`: 500
- Idle Sessions: 390 (most are `idle` or `idle in transaction` from application poolers)
- Longest Idle Session: `pid: 1045` (idle for 34 minutes, query: `SELECT * FROM session_tokens WHERE token = $1`)

## Live Context & Error Logs
```text
2026-06-15 15:59:45.981 UTC [510] FATAL:  sorry, too many clients already
2026-06-15 15:59:50.012 UTC [512] FATAL:  sorry, too many clients already
2026-06-15 16:00:01.129 UTC [514] WARNING: connection pooler limit reached on application node app-web-04
```

## Recommended Runbook Reference
Please reference the **PostgreSQL: High Connection Count Runbook** or **Database Connection Pool Exhaustion** runbook for active remediation steps.
""",
        "postgresql,connections,limit,alert,prometheus,live"
    ),
    (
        "Prometheus Alert: RDSCPUUtilizationHigh",
        """# Prometheus Alert: RDSCPUUtilizationHigh

## Alert Information
- **Alert Name**: RDSCPUUtilizationHigh
- **Severity**: warning
- **Instance**: rds-pg-prod-primary.c1234.us-east-1.rds.amazonaws.com
- **Database**: prod_analytics
- **Timestamp**: 2026-06-15T16:10:00Z
- **Status**: firing
- **Source**: CloudWatch / Prometheus

## Alert Summary
RDS instance CPU utilization is elevated at 98.2%. This exceeds the warning threshold of 80% for 5 consecutive minutes.

## Diagnostic Data / Metrics
- CPU Utilization: 98.2% (User: 95.0%, System: 3.2%)
- Read IOPS: 4,500
- Write IOPS: 200
- Database Load (Active Sessions): 15 active queries

## Live Context & Running Queries
```sql
-- PID: 4215, Duration: 245 seconds, State: active
SELECT customer_id, SUM(order_amount) 
FROM orders 
WHERE status = 'completed' AND created_at > '2023-01-01' 
GROUP BY customer_id;
-- Plan analysis: Seq Scan on orders (cost=0.00..54210.00 rows=1524310 width=16)
```

## Recommended Runbook Reference
Please reference the **RDS: High CPU Utilization** runbook or **PostgreSQL: Slow Query Investigation Runbook** for active remediation steps.
""",
        "rds,aws,cpu,alert,prometheus,live"
    ),
    (
        "Prometheus Alert: RDSDiskSpaceCritical",
        """# Prometheus Alert: RDSDiskSpaceCritical

## Alert Information
- **Alert Name**: RDSDiskSpaceCritical
- **Severity**: critical
- **Instance**: rds-pg-prod-primary.c1234.us-east-1.rds.amazonaws.com
- **Database**: production_db
- **Timestamp**: 2026-06-15T16:15:00Z
- **Status**: firing
- **Source**: CloudWatch / Prometheus

## Alert Summary
Free storage space on RDS database instance has dropped below 5% (currently 4.1% / 8.2 GB free out of 200 GB allocated). Storage Autoscaling limit has been hit.

## Diagnostic Data / Metrics
- `FreeStorageSpace`: 8,804,686,848 bytes (8.2 GB)
- Allocated Storage: 200 GB
- Storage Autoscaling Max Limit: 200 GB (Limit reached, cannot auto-grow)
- Disk Fill Rate: 2.1 GB/hour (estimated time to exhaustion: ~3.9 hours)

## Live Context & Error Logs
```text
2026-06-15 16:13:00.124 UTC [702] WARNING: disk space low, autovacuum is blocked on table 'audit_logs'
2026-06-15 16:14:12.890 UTC [702] ERROR: could not write block to table 'activity_events': temporary file limit reached or out of disk space
```

## Recommended Runbook Reference
Please reference the **RDS: Disk Space Critical** runbook or **RDS: Storage Space Critical - Investigation and Remediation** runbook for active remediation steps.
""",
        "rds,aws,disk,storage,alert,prometheus,live"
    ),
    (
        "Prometheus Alert: PostgreSQLDeadlockDetected",
        """# Prometheus Alert: PostgreSQLDeadlockDetected

## Alert Information
- **Alert Name**: PostgreSQLDeadlockDetected
- **Severity**: warning
- **Instance**: db-primary.prod.internal:5432
- **Database**: production_db
- **Timestamp**: 2026-06-15T16:20:00Z
- **Status**: firing
- **Source**: Prometheus Alertmanager

## Alert Summary
PostgreSQL engine logs indicate a deadlock cycle was detected and resolved by rolling back a transaction. Spikes in deadlock counts detected.

## Diagnostic Data / Metrics
- `pg_stat_database_deadlocks`: 14 deadlocks in last 10 minutes
- Target Tables: `orders`, `order_items`, `inventory`
- Deadlock cycle detected between PID 8942 and PID 8945.

## Live Context & Deadlock Logs
```text
2026-06-15 16:19:45.109 UTC [8942] ERROR:  deadlock detected
2026-06-15 16:19:45.109 UTC [8942] DETAIL:  Process 8942 waits for ShareLock on transaction 124502; blocked by process 8945.
	Process 8945 waits for ExclusiveLock on relation 16421 of database 16384; blocked by process 8942.
	Process 8942: UPDATE inventory SET quantity = quantity - 1 WHERE item_id = 4210;
	Process 8945: UPDATE orders SET status = 'processing' WHERE id = 100412;
2026-06-15 16:19:45.110 UTC [8942] HINT:  See server log for query details.
2026-06-15 16:19:45.110 UTC [8942] STATEMENT:  UPDATE inventory SET quantity = quantity - 1 WHERE item_id = 4210;
```

## Recommended Runbook Reference
Please reference the **PostgreSQL: Deadlock Detection and Resolution Runbook** for active diagnostic commands and code fixes.
""",
        "postgresql,deadlock,alert,prometheus,live"
    )
]

@dataclass
class AlertDocumentSpec:
    title: str
    content: str
    tags: str

def main() -> None:
    print("=" * 60)
    print("  Prometheus DB Alert Simulation and Ingestion")
    print("=" * 60)

    # ------------------------------------------------------------------
    # Bootstrap settings & embedding provider
    # ------------------------------------------------------------------
    print("\n[1/3] Initializing embedding provider...")
    settings = Settings()
    if settings.embedding_provider == "gemini":
        if not settings.gemini_api_key:
            print("ERROR: GEMINI_API_KEY is not set in environment or .env file.")
            sys.exit(1)
        embedding_provider = GeminiEmbeddingProvider(
            api_key=settings.gemini_api_key,
            model_name=settings.embedding_model,
            dimension=settings.embedding_dimension,
        )
    else:
        embedding_provider = LocalEmbeddingProvider(
            model_name=settings.embedding_model
        )
    print(f"      Provider: {embedding_provider.provider_name}")
    print(f"      Model: {embedding_provider.model_name} (dim={embedding_provider.dimension})")

    chunker = StructureAwareChunker()
    pipeline = IngestionPipeline(
        parsers=[MarkdownParser(), TextParser()],
        chunker=chunker,
        embedding_provider=embedding_provider,
    )

    # ------------------------------------------------------------------
    # Database setup
    # ------------------------------------------------------------------
    print("\n[2/3] Connecting to database...")
    db_url = settings.database_url.replace("postgresql+asyncpg", "postgresql+psycopg")
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    SessionFactory = sessionmaker(bind=engine)
    print(f"      DB URL: {db_url}")

    # ------------------------------------------------------------------
    # Prepare documents
    # ------------------------------------------------------------------
    print("\n[3/3] Ingesting simulated alerts into RAG pipeline...")
    print("-" * 60)

    ingested = 0
    skipped = 0
    failed = 0
    total_chunks = 0
    total_embeddings = 0

    with SessionFactory() as session:
        for i, (title, content, tags) in enumerate(SIMULATED_ALERTS, 1):
            print(f"  [{i:02d}/{len(SIMULATED_ALERTS):02d}] {title:<55}", end="")
            try:
                result = pipeline.ingest(
                    session=session,
                    raw_content=content,
                    source_type="markdown",
                    title=title,
                    uri=f"prometheus://alertmanager/{title.split(': ')[-1]}",
                    metadata={
                        "tags": tags,
                        "source": "prometheus-alert-simulation",
                        "type": "prometheus-alert",
                        "ingested_at": datetime.now(UTC).isoformat(),
                    },
                )
                if result.is_duplicate:
                    print(" [DUPLICATE]")
                    skipped += 1
                else:
                    print(
                        f" [OK] {result.chunk_count} chunks, "
                        f"{result.embeddings_created} embeddings"
                    )
                    ingested += 1
                    total_chunks += result.chunk_count
                    total_embeddings += result.embeddings_created
            except Exception as e:
                print(f" [ERROR] ERROR: {e}")
                failed += 1

    print("\n" + "=" * 60)
    print("  SIMULATION COMPLETE")
    print("=" * 60)
    print(f"  Alerts ingested    : {ingested}")
    print(f"  Duplicates skipped : {skipped}")
    print(f"  Failures           : {failed}")
    print(f"  Total chunks       : {total_chunks}")
    print(f"  Total embeddings   : {total_embeddings}")
    print(f"  Database           : {db_url}")
    print("=" * 60)

if __name__ == "__main__":
    main()
