# ruff: noqa: E501
"""
DB Runbooks and Alerts Data Ingestion Script
============================================
Downloads real-world database operational knowledge from authoritative open-source
sources, cleans/transforms the raw data, and ingests it into the RAG system.

Sources:
  1. Qonto Database Monitoring Framework – PostgreSQL & RDS runbooks
     (https://github.com/qonto/database-monitoring-framework)
  2. PostgreSQL official documentation – error codes, DBA tasks
     (https://www.postgresql.org/docs/current/)
  3. AWS RDS best practices and common DBA procedures
     (https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/)
  4. Curated hand-crafted runbooks covering common DB alarms with
     diagnostic commands and remediation steps.

Usage:
    uv run --env-file .env scripts/ingest_db_runbooks.py
"""

from __future__ import annotations

import re
import sys
import time
import urllib.request
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

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

GITHUB_BASE = (
    "https://raw.githubusercontent.com/qonto/database-monitoring-framework/main/content"
)

# PostgreSQL runbooks from Qonto framework
PG_RUNBOOKS = [
    (
        "PostgreSQL: Inactive Logical Replication Slot",
        f"{GITHUB_BASE}/runbooks/postgresql/PostgreSQLInactiveLogicalReplicationSlot.md",
        "postgresql,replication,alert,runbook",
    ),
    (
        "PostgreSQL: Inactive Physical Replication Slot",
        f"{GITHUB_BASE}/runbooks/postgresql/PostgreSQLInactivePhysicalReplicationSlot.md",
        "postgresql,replication,alert,runbook",
    ),
    (
        "PostgreSQL: Invalid Index Detected",
        f"{GITHUB_BASE}/runbooks/postgresql/PostgreSQLInvalidIndex.md",
        "postgresql,index,alert,runbook",
    ),
    (
        "PostgreSQL: Long Running Queries Alert",
        f"{GITHUB_BASE}/runbooks/postgresql/PostgreSQLLongRunningQueries.md",
        "postgresql,queries,performance,alert,runbook",
    ),
    (
        "PostgreSQL: Max Connections Reached",
        f"{GITHUB_BASE}/runbooks/postgresql/PostgreSQLMaxConnections.md",
        "postgresql,connections,alert,runbook",
    ),
    (
        "PostgreSQL: Replication Slot Storage Limit",
        f"{GITHUB_BASE}/runbooks/postgresql/PostgreSQLReplicationSlotStorageLimit.md",
        "postgresql,replication,storage,alert,runbook",
    ),
    (
        "PostgreSQL: SQL Exporter Down",
        f"{GITHUB_BASE}/runbooks/postgresql/SQLExporterDown.md",
        "postgresql,monitoring,exporter,alert,runbook",
    ),
    (
        "PostgreSQL: SQL Exporter Missing Target",
        f"{GITHUB_BASE}/runbooks/postgresql/SQLExporterMissingTarget.md",
        "postgresql,monitoring,exporter,alert,runbook",
    ),
    (
        "PostgreSQL: SQL Exporter Scraping Limit",
        f"{GITHUB_BASE}/runbooks/postgresql/SQLExporterScrapingLimit.md",
        "postgresql,monitoring,exporter,alert,runbook",
    ),
]

# RDS runbooks from Qonto framework
RDS_RUNBOOKS = [
    (
        "RDS: Available Memory Low",
        f"{GITHUB_BASE}/runbooks/rds/RDSAvailableMemory.md",
        "rds,aws,memory,alert,runbook",
    ),
    (
        "RDS: CA Certificate Expiring Soon",
        f"{GITHUB_BASE}/runbooks/rds/RDSCACertificateCloseToExpiration.md",
        "rds,aws,ssl,certificate,alert,runbook",
    ),
    (
        "RDS: High CPU Utilization",
        f"{GITHUB_BASE}/runbooks/rds/RDSCPUUtilization.md",
        "rds,aws,cpu,performance,alert,runbook",
    ),
    (
        "RDS: Disk AutoScaling Limit Reached",
        f"{GITHUB_BASE}/runbooks/rds/RDSDiskAutoScalingLimit.md",
        "rds,aws,disk,storage,alert,runbook",
    ),
    (
        "RDS: Disk Space Critical",
        f"{GITHUB_BASE}/runbooks/rds/RDSDiskSpaceLimit.md",
        "rds,aws,disk,storage,alert,runbook",
    ),
    (
        "RDS: Disk Space Prediction Alert",
        f"{GITHUB_BASE}/runbooks/rds/RDSDiskSpacePrediction.md",
        "rds,aws,disk,storage,prediction,alert,runbook",
    ),
    (
        "RDS: Exporter Down",
        f"{GITHUB_BASE}/runbooks/rds/RDSExporterDown.md",
        "rds,aws,monitoring,exporter,alert,runbook",
    ),
    (
        "RDS: Exporter Errors",
        f"{GITHUB_BASE}/runbooks/rds/RDSExporterErrors.md",
        "rds,aws,monitoring,exporter,alert,runbook",
    ),
    (
        "RDS: Exporter Missing Metrics",
        f"{GITHUB_BASE}/runbooks/rds/RDSExporterMissingMetrics.md",
        "rds,aws,monitoring,exporter,alert,runbook",
    ),
    (
        "RDS: Forced Maintenance Window Pending",
        f"{GITHUB_BASE}/runbooks/rds/RDSForcedMaintenance.md",
        "rds,aws,maintenance,alert,runbook",
    ),
    (
        "RDS: High IOPS Utilization",
        f"{GITHUB_BASE}/runbooks/rds/RDSIOPSUtilization.md",
        "rds,aws,iops,performance,alert,runbook",
    ),
    (
        "RDS: Low Disk Space Count (Multi-Instance)",
        f"{GITHUB_BASE}/runbooks/rds/RDSLowDiskSpaceCount.md",
        "rds,aws,disk,storage,alert,runbook",
    ),
    (
        "RDS: High Memory Utilization",
        f"{GITHUB_BASE}/runbooks/rds/RDSMemoryUtilization.md",
        "rds,aws,memory,performance,alert,runbook",
    ),
    (
        "RDS: Non-CPU Utilization High",
        f"{GITHUB_BASE}/runbooks/rds/RDSNonCPUUtilization.md",
        "rds,aws,performance,alert,runbook",
    ),
    (
        "RDS: PostgreSQL Transaction ID Wraparound Warning",
        f"{GITHUB_BASE}/runbooks/rds/RDSPostgreSQLMaximumUsedTransaction.md",
        "rds,aws,postgresql,vacuum,txid,alert,runbook",
    ),
    (
        "RDS: Instance Quota Limit Warning",
        f"{GITHUB_BASE}/runbooks/rds/RDSQuotaInstanceLimit.md",
        "rds,aws,quota,alert,runbook",
    ),
    (
        "RDS: Storage Quota Limit Warning",
        f"{GITHUB_BASE}/runbooks/rds/RDSQuotaStorageLimit.md",
        "rds,aws,quota,storage,alert,runbook",
    ),
    (
        "RDS: Replication Lag Critical",
        f"{GITHUB_BASE}/runbooks/rds/RDSReplicationLag.md",
        "rds,aws,replication,lag,alert,runbook",
    ),
    (
        "RDS: High Swap Utilization",
        f"{GITHUB_BASE}/runbooks/rds/RDSSwapUtilization.md",
        "rds,aws,swap,memory,alert,runbook",
    ),
    (
        "RDS: Unapplied Parameter Changes",
        f"{GITHUB_BASE}/runbooks/rds/RDSUnappliedParameters.md",
        "rds,aws,parameters,configuration,alert,runbook",
    ),
]

# ---------------------------------------------------------------------------
# Hand-crafted expert runbooks for common DB alarms (no external dependency)
# These cover critical scenarios not fully addressed by the Qonto framework.
# ---------------------------------------------------------------------------

CURATED_RUNBOOKS: list[tuple[str, str]] = [
    (
        "PostgreSQL: Deadlock Detection and Resolution Runbook",
        """\
# PostgreSQL: Deadlock Detection and Resolution Runbook

## Alert Summary
**Alert Name**: PostgreSQLDeadlockDetected
**Severity**: Warning / Critical
**Description**: PostgreSQL has detected and rolled back one or more deadlocked
transactions. Frequent deadlocks indicate application-level lock ordering issues.

## What is a Deadlock?
A deadlock occurs when two or more transactions are each waiting for the other to
release a lock. PostgreSQL automatically detects these cycles and terminates one
transaction (the "victim"), returning error code `40P01` (deadlock_detected) to the
application.

## Symptoms
- Application logs contain: `ERROR: deadlock detected`
- `pg_stat_activity` shows transactions stuck in `Lock` wait state
- CloudWatch/Prometheus shows spikes in `pg_stat_database.deadlocks`
- Application error rate increases

## Diagnosis Steps

### Step 1: Check current deadlock count
```sql
SELECT datname, deadlocks
FROM pg_stat_database
ORDER BY deadlocks DESC;
```

### Step 2: Identify blocked and blocking processes
```sql
SELECT
    blocked.pid AS blocked_pid,
    blocked.query AS blocked_query,
    blocking.pid AS blocking_pid,
    blocking.query AS blocking_query,
    blocked.wait_event_type,
    blocked.wait_event
FROM pg_stat_activity AS blocked
JOIN pg_stat_activity AS blocking
    ON blocking.pid = ANY(pg_blocking_pids(blocked.pid))
WHERE blocked.cardinality(pg_blocking_pids(blocked.pid)) > 0;
```

### Step 3: Review PostgreSQL logs for deadlock graphs
```bash
grep -A 20 "deadlock detected" /var/log/postgresql/postgresql-*.log | tail -100
```
On RDS, check CloudWatch Logs → Log Groups → `/aws/rds/instance/{db-name}/postgresql`.

### Step 4: Identify the tables involved
Look at the deadlock graph in the logs to find:
- Which tables are involved
- What operations caused the conflict (UPDATE, DELETE, INSERT)

## Remediation

### Short-term: Kill blocking sessions
```sql
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE state = 'idle in transaction'
  AND query_start < NOW() - INTERVAL '10 minutes';
```

### Long-term: Fix the application
1. **Consistent lock ordering**: Ensure all transactions acquire locks on the same
   tables in the same order.
2. **Reduce transaction scope**: Keep transactions short; avoid user interaction
   inside transactions.
3. **Use SELECT FOR UPDATE SKIP LOCKED** for queue-style workloads.
4. **Retry logic**: Implement retry on `40P01` in application code.
5. **Use advisory locks** for application-level coordination.

## Prevention
- Enable `log_lock_waits = on` and `deadlock_timeout = 1s` in postgresql.conf
- Monitor `pg_stat_database.deadlocks` with alerting thresholds
- Review EXPLAIN ANALYZE output for queries that frequently conflict

## References
- PostgreSQL Docs: https://www.postgresql.org/docs/current/explicit-locking.html
- Error Code 40P01: deadlock_detected
""",
    ),
    (
        "PostgreSQL: VACUUM and Autovacuum Runbook",
        """\
# PostgreSQL: VACUUM and Autovacuum Runbook

## Alert Summary
**Alert Name**: PostgreSQLAutovacuumNotRunning / TransactionIDWraparound
**Severity**: Warning → Critical (wraparound)
**Description**: Autovacuum is not keeping up with dead tuple accumulation or the
transaction ID (XID) counter is dangerously close to wraparound.

## Background
PostgreSQL uses MVCC (Multi-Version Concurrency Control). Every UPDATE and DELETE
creates "dead tuples" that must be cleaned by VACUUM. Autovacuum is the background
daemon that handles this automatically. Failure to vacuum leads to:
1. **Table bloat**: Wasted disk space, degraded query performance
2. **XID wraparound**: At ~2 billion transactions, PostgreSQL will refuse all writes
   to prevent data corruption (emergency shutdown mode)

## Symptoms
- Dead tuple count rising in `pg_stat_user_tables`
- `age(relfrozenxid)` approaching 200 million (warning) or 1.5 billion (critical)
- `autovacuum_freeze_max_age` threshold breached
- Tables in `pg_stat_user_tables` with very old `last_autovacuum` timestamps
- Alert: "RDSPostgreSQLMaximumUsedTransaction" firing

## Diagnosis Steps

### Step 1: Check tables most in need of vacuuming
```sql
SELECT
    schemaname,
    tablename,
    n_dead_tup,
    n_live_tup,
    ROUND(n_dead_tup::NUMERIC / NULLIF(n_live_tup + n_dead_tup, 0) * 100, 2)
        AS dead_pct,
    last_autovacuum,
    last_analyze
FROM pg_stat_user_tables
ORDER BY n_dead_tup DESC
LIMIT 20;
```

### Step 2: Check XID age (wraparound risk)
```sql
SELECT
    datname,
    age(datfrozenxid) AS xid_age,
    2000000000 - age(datfrozenxid) AS xids_remaining
FROM pg_database
ORDER BY age(datfrozenxid) DESC;
```

### Step 3: Check if autovacuum is currently running
```sql
SELECT pid, datname, relid::regclass, phase, heap_blks_total, heap_blks_scanned
FROM pg_stat_progress_vacuum;
```

### Step 4: Check autovacuum settings
```sql
SHOW autovacuum_vacuum_cost_delay;
SHOW autovacuum_vacuum_scale_factor;
SHOW autovacuum_vacuum_threshold;
```

## Remediation

### Manual VACUUM for immediate relief
```sql
-- Standard vacuum (reclaims dead tuples, doesn't shrink file)
VACUUM ANALYZE schema.table_name;

-- Full vacuum (reclaims disk space, requires exclusive lock - use with caution)
VACUUM FULL schema.table_name;

-- Freeze to advance frozen XID (for wraparound prevention)
VACUUM FREEZE schema.table_name;
```

### Tune autovacuum for high-write tables
```sql
ALTER TABLE high_write_table SET (
    autovacuum_vacuum_scale_factor = 0.01,
    autovacuum_vacuum_threshold = 100,
    autovacuum_analyze_scale_factor = 0.01
);
```

### On RDS: Adjust parameter group
- `autovacuum_vacuum_cost_delay`: Reduce to 2ms for faster autovacuum
- `autovacuum_max_workers`: Increase to 5-6 for busy databases
- `maintenance_work_mem`: Increase to 1GB per worker for faster vacuums

## Emergency: XID Wraparound Imminent
If `age(datfrozenxid)` > 1.9 billion:
1. Stop all non-critical write traffic immediately
2. Run `VACUUM FREEZE` on the oldest table manually
3. Scale up the instance if I/O is the bottleneck
4. Consider setting `autovacuum_freeze_max_age = 150000000` proactively

## References
- PostgreSQL Docs: https://www.postgresql.org/docs/current/routine-vacuuming.html
- Transaction ID Wraparound: https://www.postgresql.org/docs/current/routine-vacuuming.html#VACUUM-FOR-WRAPAROUND
""",
    ),
    (
        "PostgreSQL: High Connection Count Runbook",
        """\
# PostgreSQL: High Connection Count Runbook

## Alert Summary
**Alert Name**: PostgreSQLMaxConnections / RDSConnectionsHigh
**Severity**: Warning (>80%) / Critical (>95%)
**Description**: The number of active connections is approaching or has exceeded the
`max_connections` limit. New connections will be refused when the limit is hit.

## Background
PostgreSQL maintains a dedicated backend process per connection. Exceeding
`max_connections` causes `FATAL: sorry, too many clients already` errors.
On RDS, the default `max_connections` is formula-based on instance memory:
  LEAST({DBInstanceClassMemory/9531392}, 5000)

## Symptoms
- Application errors: `FATAL: sorry, too many clients already`
- `pg_stat_activity` count near `max_connections` value
- Prometheus alert `PostgreSQLMaxConnections` or `RDSConnectionsHigh` firing
- Connection pool exhausted errors in application logs

## Diagnosis Steps

### Step 1: Check current connection usage
```sql
SELECT COUNT(*) AS total_connections,
       MAX(setting::int) AS max_connections,
       ROUND(COUNT(*) * 100.0 / MAX(setting::int), 1) AS usage_pct
FROM pg_stat_activity, pg_settings
WHERE name = 'max_connections';
```

### Step 2: Break down by state and user
```sql
SELECT usename, state, COUNT(*) AS cnt
FROM pg_stat_activity
GROUP BY usename, state
ORDER BY cnt DESC;
```

### Step 3: Find idle connections (wasting slots)
```sql
SELECT pid, usename, application_name, client_addr,
       state, state_change, query_start,
       NOW() - state_change AS idle_duration
FROM pg_stat_activity
WHERE state = 'idle'
ORDER BY idle_duration DESC
LIMIT 20;
```

### Step 4: Check for "idle in transaction" (most dangerous)
```sql
SELECT pid, usename, application_name, state,
       NOW() - query_start AS duration, query
FROM pg_stat_activity
WHERE state = 'idle in transaction'
ORDER BY duration DESC;
```

## Remediation

### Immediate: Terminate idle connections
```sql
-- Terminate idle connections older than 10 minutes
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE state = 'idle'
  AND state_change < NOW() - INTERVAL '10 minutes'
  AND pid <> pg_backend_pid();
```

### Short-term: Implement connection pooling
Deploy PgBouncer in front of PostgreSQL:
- `pool_mode = transaction` for most workloads
- Set `max_client_conn` per application need
- Set `default_pool_size` = 20-30 per database

### RDS-specific: Increase max_connections
Modify the Parameter Group:
```
max_connections = {DBInstanceClassMemory/7864320}
```
Note: This requires a reboot. Scale the instance class first if memory-constrained.

### Long-term: Connection pooling architecture
1. **RDS Proxy**: AWS managed connection pooler, no reboot needed
2. **PgBouncer on EC2/ECS**: More control, lower latency
3. **Application-side pool**: Use connection pool settings in ORMs
   (e.g., SQLAlchemy `pool_size=10, max_overflow=5`)

### Set idle connection timeout
```sql
ALTER SYSTEM SET idle_in_transaction_session_timeout = '10min';
SELECT pg_reload_conf();
```

## References
- PgBouncer: https://www.pgbouncer.org/
- AWS RDS Proxy: https://aws.amazon.com/rds/proxy/
- PostgreSQL max_connections: https://www.postgresql.org/docs/current/runtime-config-connection.html
""",
    ),
    (
        "PostgreSQL: Slow Query Investigation Runbook",
        """\
# PostgreSQL: Slow Query Investigation Runbook

## Alert Summary
**Alert Name**: PostgreSQLLongRunningQueries / SlowQueryDetected
**Severity**: Warning (>30s) / Critical (>5min)
**Description**: One or more queries have been running for an extended period,
potentially blocking other operations and degrading overall database performance.

## Background
Long-running queries:
1. Hold locks preventing other transactions from proceeding
2. Consume CPU and I/O resources
3. Block autovacuum from reclaiming dead tuples
4. Increase replication lag on replicas

## Diagnosis Steps

### Step 1: Find all long-running queries
```sql
SELECT
    pid,
    now() - pg_stat_activity.query_start AS duration,
    query,
    state,
    wait_event_type,
    wait_event,
    usename,
    application_name,
    client_addr
FROM pg_stat_activity
WHERE (now() - pg_stat_activity.query_start) > INTERVAL '30 seconds'
  AND state != 'idle'
ORDER BY duration DESC;
```

### Step 2: Check if query is waiting on a lock
```sql
SELECT
    blocked.pid AS blocked_pid,
    blocked.query AS blocked_query,
    blocking.pid AS blocking_pid,
    blocking.query AS blocking_query
FROM pg_stat_activity blocked
JOIN pg_stat_activity blocking
    ON blocking.pid = ANY(pg_blocking_pids(blocked.pid))
WHERE cardinality(pg_blocking_pids(blocked.pid)) > 0;
```

### Step 3: Check query execution plan (if still running)
```sql
SELECT pid, query_start, query
FROM pg_stat_activity
WHERE pid = <target_pid>;

-- Get the actual execution plan
SELECT * FROM pg_stat_activity WHERE pid = <target_pid>;
```

### Step 4: Identify problematic query patterns via pg_stat_statements
```sql
SELECT
    query,
    calls,
    total_exec_time,
    mean_exec_time,
    max_exec_time,
    rows,
    shared_blks_hit,
    shared_blks_read
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 20;
```

## Remediation

### Cancel a query (graceful)
```sql
SELECT pg_cancel_backend(<pid>);
```
This sends SIGINT to the backend. The query will be rolled back cleanly.

### Terminate a session (forceful)
```sql
SELECT pg_terminate_backend(<pid>);
```
Use this if cancel doesn't work within 30 seconds.

### Fix slow queries permanently
1. **Add missing index**: Use `EXPLAIN (ANALYZE, BUFFERS)` to find sequential scans
2. **Update table statistics**: `ANALYZE schema.table_name;`
3. **Rewrite query**: Avoid `SELECT *`, use pagination, push filters down
4. **Enable pg_stat_statements**: Add to `shared_preload_libraries`
5. **Set statement_timeout**: Prevents runaway queries
   ```sql
   ALTER ROLE app_user SET statement_timeout = '60s';
   ```

### Prevent long-running queries
```sql
-- Per-role timeout
ALTER ROLE readonly_user SET statement_timeout = '30s';

-- System-wide lock wait timeout
ALTER SYSTEM SET lock_timeout = '10s';
SELECT pg_reload_conf();
```

## References
- pg_stat_activity: https://www.postgresql.org/docs/current/monitoring-stats.html
- pg_stat_statements: https://www.postgresql.org/docs/current/pgstatstatements.html
- EXPLAIN ANALYZE: https://www.postgresql.org/docs/current/sql-explain.html
""",
    ),
    (
        "RDS: Storage Space Critical – Investigation and Remediation",
        """\
# RDS: Storage Space Critical – Investigation and Remediation

## Alert Summary
**Alert Name**: RDSDiskSpaceLimit / FreeStorageSpace
**Severity**: Warning (<20%) / Critical (<10% or <5GB)
**CloudWatch Metric**: `FreeStorageSpace` (in bytes)
**Description**: The RDS instance is running low on storage. If storage fills
completely, the database will become read-only and connections will start failing.

## Immediate Actions (Time-Sensitive!)

### Step 1: Check current free space
```bash
aws cloudwatch get-metric-statistics \
    --namespace AWS/RDS \
    --metric-name FreeStorageSpace \
    --dimensions Name=DBInstanceIdentifier,Value=<your-db-id> \
    --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
    --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
    --period 60 \
    --statistics Minimum \
    --output table
```

### Step 2: Check RDS storage allocation
```bash
aws rds describe-db-instances \
    --db-instance-identifier <your-db-id> \
    --query 'DBInstances[0].{AllocatedStorage:AllocatedStorage,StorageType:StorageType}'
```

## Database-Level Diagnosis

### Find the largest tables (PostgreSQL)
```sql
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS total_size,
    pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) AS table_size,
    pg_size_pretty(pg_indexes_size(schemaname||'.'||tablename)) AS index_size
FROM pg_tables
WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
LIMIT 20;
```

### Find largest tables (MySQL)
```sql
SELECT
    table_schema AS db_name,
    table_name,
    ROUND((data_length + index_length) / 1024 / 1024, 2) AS size_mb
FROM information_schema.tables
ORDER BY (data_length + index_length) DESC
LIMIT 20;
```

### Check for bloated tables (PostgreSQL)
```sql
SELECT schemaname, tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size,
    n_dead_tup,
    n_live_tup
FROM pg_stat_user_tables
ORDER BY n_dead_tup DESC
LIMIT 10;
```

## Remediation

### Option 1: Increase RDS Storage (Online – No Downtime)
```bash
aws rds modify-db-instance \
    --db-instance-identifier <your-db-id> \
    --allocated-storage <new-size-in-gb> \
    --apply-immediately
```
- Storage can only be increased (not decreased)
- Minimum 10% increase required
- Allow 6+ hours for storage optimization to complete
- Enable Storage Autoscaling to prevent recurrence

### Option 2: Enable Storage Autoscaling
```bash
aws rds modify-db-instance \
    --db-instance-identifier <your-db-id> \
    --max-allocated-storage 1000 \
    --apply-immediately
```

### Option 3: Reclaim space immediately (PostgreSQL)
```sql
-- VACUUM dead tuples (no lock)
VACUUM ANALYZE;

-- Drop obsolete or temporary tables
DROP TABLE IF EXISTS temp_export_20231201;

-- Truncate log/audit tables (if safe to do so)
TRUNCATE TABLE audit_log_archive;
```

### Option 4: Archive old data
```sql
-- Move old records to an archive table (then delete from main)
INSERT INTO orders_archive
SELECT * FROM orders WHERE created_at < NOW() - INTERVAL '2 years';

DELETE FROM orders WHERE created_at < NOW() - INTERVAL '2 years';

VACUUM ANALYZE orders;
```

## Post-Incident
1. Set up Storage Autoscaling with a reasonable maximum
2. Add CloudWatch alarm at 30%, 20%, and 10% thresholds
3. Set up weekly scheduled job to VACUUM and archive old data
4. Review retention policies for log/audit tables

## References
- AWS RDS Storage: https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_PIOPS.StorageTypes.html
- Autoscaling Storage: https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_PIOPS.Autoscaling.html
""",
    ),
    (
        "RDS: High CPU Utilization – Investigation and Remediation",
        """\
# RDS: High CPU Utilization – Investigation and Remediation

## Alert Summary
**Alert Name**: RDSCPUUtilization
**Severity**: Warning (>80% for 5min) / Critical (>95% for 2min)
**CloudWatch Metric**: `CPUUtilization`
**Description**: Database CPU is elevated. Sustained high CPU causes query latency
spikes, connection timeouts, and can cascade into application outages.

## Common Root Causes
1. Missing indexes causing sequential scans on large tables
2. N+1 query anti-patterns (many small queries instead of one JOIN)
3. Sudden traffic spike (new feature deployment, marketing campaign)
4. VACUUM or pg_dump running during peak hours
5. Inefficient query plan due to stale statistics
6. Checkpoint storms from high write volume

## Diagnosis Steps

### Step 1: Check current CPU-consuming queries (PostgreSQL)
```sql
SELECT pid,
       now() - query_start AS duration,
       ROUND(100.0 * (extract(epoch from now()) -
             extract(epoch from query_start)) /
             NULLIF(extract(epoch from now()) -
             extract(epoch from backend_start), 0), 2) AS cpu_pct_est,
       state,
       query
FROM pg_stat_activity
WHERE state != 'idle'
  AND query_start IS NOT NULL
ORDER BY duration DESC
LIMIT 20;
```

### Step 2: Use AWS Performance Insights
```
RDS Console → Performance Insights → DB Load by Wait → Top SQL
```
Sort by `db load` to find the biggest contributors.

### Step 3: Check for full table scans
```sql
SELECT relname, seq_scan, seq_tup_read,
       idx_scan, idx_tup_fetch,
       ROUND(100.0 * seq_scan / NULLIF(seq_scan + idx_scan, 0), 2) AS seq_scan_pct
FROM pg_stat_user_tables
WHERE seq_scan > 100
ORDER BY seq_tup_read DESC
LIMIT 15;
```

### Step 4: Identify missing indexes
```sql
SELECT
    schemaname,
    tablename,
    attname AS column_name,
    n_distinct,
    correlation
FROM pg_stats
WHERE tablename IN (
    SELECT relname FROM pg_stat_user_tables
    ORDER BY seq_tup_read DESC LIMIT 5
)
ORDER BY n_distinct;
```

### Step 5: Check checkpoint behavior
```sql
SELECT checkpoints_timed, checkpoints_req,
       checkpoint_write_time, checkpoint_sync_time,
       buffers_checkpoint, buffers_clean, buffers_backend
FROM pg_stat_bgwriter;
```

## Remediation

### Immediate: Identify and kill the top CPU query
```sql
SELECT pg_cancel_backend(<pid>);
```

### Short-term: Add missing indexes
```sql
-- Create index without blocking reads/writes
CREATE INDEX CONCURRENTLY idx_orders_user_id ON orders(user_id);
```

### Short-term: Update stale statistics
```sql
ANALYZE schema.table_name;
-- Or system-wide
ANALYZE;
```

### Long-term: Enable pg_stat_statements
Add to Parameter Group:
```
shared_preload_libraries = pg_stat_statements
pg_stat_statements.max = 10000
pg_stat_statements.track = all
```

Then find the most expensive queries:
```sql
SELECT query, calls, total_exec_time, mean_exec_time
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 10;
```

### RDS: Vertical Scaling
```bash
aws rds modify-db-instance \
    --db-instance-identifier <your-db-id> \
    --db-instance-class db.r6g.4xlarge \
    --apply-immediately
```

### Scale reads to a read replica
Direct read traffic to a Read Replica for heavy reporting queries.

## References
- AWS Performance Insights: https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_PerfInsights.html
- PostgreSQL explain: https://www.postgresql.org/docs/current/sql-explain.html
""",
    ),
    (
        "PostgreSQL: Replication Lag Runbook",
        """\
# PostgreSQL: Replication Lag Runbook

## Alert Summary
**Alert Name**: RDSReplicationLag / PostgreSQLReplicationLag
**Severity**: Warning (>30s) / Critical (>5min)
**Metric**: `ReplicaLag` (RDS) or `pg_replication_slots.confirmed_flush_lsn` (self-managed)
**Description**: A standby replica is falling behind the primary, risking data loss
on failover and serving stale reads if applications use the replica.

## Common Root Causes
1. Heavy write load on primary overwhelming the replica's I/O
2. Long-running queries on the replica causing conflict with replication
3. Inactive or stale replication slot preventing WAL cleanup (slot bloat)
4. Replica I/O or CPU bottleneck (underpowered instance class)
5. Network bandwidth saturation between primary and replica

## Diagnosis Steps

### Step 1: Check replication status on the primary
```sql
SELECT
    client_addr,
    application_name,
    state,
    sent_lsn,
    write_lsn,
    flush_lsn,
    replay_lsn,
    write_lag,
    flush_lag,
    replay_lag,
    sync_state
FROM pg_stat_replication;
```

### Step 2: Check lag in bytes (WAL not yet applied)
```sql
SELECT
    pid,
    client_addr,
    pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn) AS lag_bytes
FROM pg_stat_replication;
```

### Step 3: On the replica – check for conflicts
```sql
SELECT datname, conflicts
FROM pg_stat_database
WHERE conflicts > 0;
```

### Step 4: Check for blocking queries on the replica
```sql
SELECT pid, now() - query_start AS duration, query, wait_event_type, wait_event
FROM pg_stat_activity
WHERE state != 'idle'
ORDER BY duration DESC;
```

### Step 5: Check replication slots
```sql
SELECT slot_name, slot_type, active, restart_lsn,
       pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn) AS lag_bytes
FROM pg_replication_slots;
```

## Remediation

### Immediate: Check and cancel long-running replica queries
On the replica:
```sql
SELECT pg_cancel_backend(pid)
FROM pg_stat_activity
WHERE now() - query_start > INTERVAL '5 minutes';
```

### Tune replica conflict resolution
On the replica (postgresql.conf):
```
max_standby_streaming_delay = 60s  -- Allow replica 60s to finish conflicting queries
hot_standby_feedback = on          -- Prevent primary from vacuuming rows replica needs
```

### Drop inactive replication slots (if causing WAL bloat)
```sql
-- First verify the slot is truly no longer needed
SELECT slot_name, active, pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn)
FROM pg_replication_slots;

-- Drop inactive slot
SELECT pg_drop_replication_slot('slot_name_here');
```

### RDS: Check replica instance class
If the replica is a smaller instance than the primary, I/O may be the bottleneck:
```bash
aws rds modify-db-instance \
    --db-instance-identifier <replica-id> \
    --db-instance-class db.r6g.4xlarge \
    --apply-immediately
```

### Long-term: Distribute write load
- Use table partitioning to distribute I/O
- Consider multi-AZ with dedicated read replicas per region
- Use logical replication for selective table sync

## References
- Streaming Replication: https://www.postgresql.org/docs/current/warm-standby.html
- Replication Slots: https://www.postgresql.org/docs/current/warm-standby.html#STREAMING-REPLICATION-SLOTS
""",
    ),
    (
        "Database Connection Pool Exhaustion – Detection and Resolution",
        """\
# Database Connection Pool Exhaustion – Detection and Resolution

## Alert Summary
**Alert Name**: DBConnectionPoolExhausted / AppConnectionTimeout
**Severity**: Critical
**Description**: The application's connection pool has been exhausted. New requests
cannot acquire a database connection, causing 500 errors and timeouts for users.

## Background
Most applications maintain a pool of pre-established database connections for
performance (connection creation is expensive). Pool exhaustion happens when:
- More application threads need connections than the pool allows
- Connections are not returned to the pool (connection leak)
- Database queries are taking longer than expected, blocking pool slots
- The pool max size is too small for the current traffic volume

## Symptoms
- Application logs: "Connection pool timeout", "No available connections"
- All API endpoints returning 500 or timing out
- Pool metrics: `pool.waiting_clients` > 0
- `pg_stat_activity` shows many "idle in transaction" or long-running queries

## Diagnosis Steps

### Step 1: Check current database connections
```sql
SELECT usename, application_name, state, COUNT(*) as cnt
FROM pg_stat_activity
GROUP BY usename, application_name, state
ORDER BY cnt DESC;
```

### Step 2: Identify "idle in transaction" (connection leaks)
```sql
SELECT pid, usename, application_name, client_addr,
       state, now() - state_change AS duration, query
FROM pg_stat_activity
WHERE state = 'idle in transaction'
ORDER BY duration DESC;
```

### Step 3: Find which application is opening too many connections
```sql
SELECT client_addr, COUNT(*) as connections
FROM pg_stat_activity
GROUP BY client_addr
ORDER BY connections DESC;
```

### Step 4: Check pool configuration (SQLAlchemy example)
Look at application configuration:
```python
engine = create_engine(
    DATABASE_URL,
    pool_size=10,        # Base connections
    max_overflow=20,     # Extra connections allowed
    pool_timeout=30,     # Seconds to wait for connection
    pool_recycle=3600,   # Recycle connections every hour
)
```

## Remediation

### Immediate: Kill leaked connections
```sql
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE state = 'idle in transaction'
  AND state_change < NOW() - INTERVAL '5 minutes';
```

### Short-term: Restart the application pod/service
If connection leaks are confirmed, restart the application to reset the pool:
```bash
kubectl rollout restart deployment/app-api
# or
systemctl restart app-service
```

### Increase pool size (temporary)
Tune the pool size to handle peak traffic:
```python
# SQLAlchemy
create_engine(url, pool_size=20, max_overflow=40)

# Django DATABASES setting
'OPTIONS': {'pool_size': 20}
```

### Implement connection pool middleware (permanent fix)
Deploy **PgBouncer** as a sidecar or centralized service:
```ini
[databases]
mydb = host=rds.amazonaws.com port=5432 dbname=mydb

[pgbouncer]
pool_mode = transaction
max_client_conn = 1000
default_pool_size = 25
server_idle_timeout = 600
```

Or use **AWS RDS Proxy** (fully managed):
```bash
aws rds create-db-proxy \
    --db-proxy-name my-rds-proxy \
    --engine-family POSTGRESQL \
    --auth '{...}' \
    --role-arn arn:aws:iam::123:role/rds-proxy-role \
    --vpc-subnet-ids subnet-xxx subnet-yyy
```

### Fix connection leaks in code
Ensure all connections are closed using context managers:
```python
# Good: context manager guarantees return to pool
with engine.connect() as conn:
    result = conn.execute(query)

# Bad: connection may not be returned if exception occurs
conn = engine.connect()
result = conn.execute(query)  # If this raises, conn leaks!
conn.close()
```

## Prevention
1. Set `idle_in_transaction_session_timeout = '2min'` in PostgreSQL
2. Enable connection pool metrics and alert on `pool.waiting > 0`
3. Use PgBouncer or RDS Proxy to multiplex connections
4. Load test with realistic concurrency before production deploys

## References
- PgBouncer Configuration: https://www.pgbouncer.org/config.html
- SQLAlchemy Pool: https://docs.sqlalchemy.org/en/14/core/pooling.html
- AWS RDS Proxy: https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/rds-proxy.html
""",
    ),
    (
        "PostgreSQL Error Codes Reference and Troubleshooting Guide",
        """\
# PostgreSQL Error Codes Reference and Troubleshooting Guide

## Overview
PostgreSQL uses 5-character SQLSTATE codes to report errors. The first 2 characters
indicate the error class; the last 3 identify the specific condition.

## Class 08 – Connection Exception
| Code  | Name                        | Common Cause / Resolution |
|-------|-----------------------------|---------------------------|
| 08000 | connection_exception        | Generic connection error   |
| 08001 | sqlclient_unable_to_establish_sqlconnection | Client cannot reach server; check host/port/firewall |
| 08003 | connection_does_not_exist   | Session was terminated; reconnect |
| 08006 | connection_failure          | Server crashed or network interrupted |
| 08P01 | protocol_violation          | Driver/version mismatch; update client library |

## Class 23 – Integrity Constraint Violation
| Code  | Name                        | Common Cause / Resolution |
|-------|-----------------------------|---------------------------|
| 23000 | integrity_constraint_violation | Catch-all constraint error |
| 23001 | restrict_violation          | FK restriction on delete; check referential integrity |
| 23502 | not_null_violation          | NULL inserted into NOT NULL column; check data |
| 23503 | foreign_key_violation       | Orphaned reference; parent row missing |
| 23505 | unique_violation             | Duplicate key; use ON CONFLICT or check for race conditions |
| 23514 | check_violation             | CHECK constraint failed; validate input data |

### Resolving 23505 (Unique Violation)
```sql
-- Find conflicting rows
SELECT *, COUNT(*) FROM table GROUP BY unique_col HAVING COUNT(*) > 1;

-- Use UPSERT to handle conflicts gracefully
INSERT INTO table (col1, col2) VALUES ($1, $2)
ON CONFLICT (unique_col) DO UPDATE SET col2 = EXCLUDED.col2;
```

## Class 25 – Invalid Transaction State
| Code  | Name                        | Common Cause / Resolution |
|-------|-----------------------------|---------------------------|
| 25000 | invalid_transaction_state   | Generic transaction error |
| 25001 | active_sql_transaction      | Cannot change isolation level mid-transaction |
| 25006 | read_only_sql_transaction   | Write attempted on read-only connection/replica |
| 25P01 | no_active_sql_transaction   | COMMIT/ROLLBACK outside transaction |
| 25P02 | in_failed_sql_transaction   | Transaction aborted; must ROLLBACK before new commands |

### Resolving 25P02 (aborted transaction)
```python
# Application must rollback before retrying
try:
    session.execute(query)
except Exception:
    session.rollback()  # MUST rollback before any new operation
    raise
```

## Class 40 – Transaction Rollback
| Code  | Name                        | Common Cause / Resolution |
|-------|-----------------------------|---------------------------|
| 40000 | transaction_rollback        | Generic rollback error |
| 40001 | serialization_failure       | Serializable conflict; retry the transaction |
| 40003 | statement_completion_unknown | Network error during commit; check if committed |
| 40P01 | deadlock_detected           | Two transactions deadlocked; retry with exponential backoff |

### Retry pattern for 40001/40P01
```python
import time

def retry_on_deadlock(fn, max_retries=3):
    for attempt in range(max_retries):
        try:
            return fn()
        except Exception as e:
            if 'deadlock' in str(e).lower() or '40P01' in str(e):
                if attempt == max_retries - 1:
                    raise
                time.sleep(0.1 * (2 ** attempt))  # exponential backoff
                continue
            raise
```

## Class 53 – Insufficient Resources
| Code  | Name                        | Common Cause / Resolution |
|-------|-----------------------------|---------------------------|
| 53000 | insufficient_resources      | Generic resource error |
| 53100 | disk_full                   | Disk full; add storage immediately |
| 53200 | out_of_memory               | OOM; reduce work_mem or scale instance |
| 53300 | too_many_connections        | max_connections exceeded; use connection pooler |
| 53400 | configuration_limit_exceeded | Exceeded configured limit |

## Class 57 – Operator Intervention
| Code  | Name                        | Common Cause / Resolution |
|-------|-----------------------------|---------------------------|
| 57000 | operator_intervention       | DBA manually killed session |
| 57014 | query_canceled              | pg_cancel_backend() or statement_timeout hit |
| 57P01 | admin_shutdown              | pg_ctl stop or server restart |
| 57P02 | crash_shutdown              | Server crashed; check logs for cause |
| 57P03 | cannot_connect_now          | Server starting up; wait and retry |
| 57P04 | database_dropped            | Database was dropped while connected |

## Class 58 – System Error
| Code  | Name                        | Common Cause / Resolution |
|-------|-----------------------------|---------------------------|
| 58000 | system_error                | OS-level error; check PostgreSQL logs |
| 58030 | io_error                    | Disk I/O error; check disk health (EBS, storage) |

## Diagnosing Unknown Errors
```sql
-- Find recent errors in PostgreSQL log
SELECT log_time, error_severity, sql_state_code, message
FROM pg_log  -- requires log_destination = 'csvlog'
WHERE error_severity IN ('ERROR', 'FATAL', 'PANIC')
ORDER BY log_time DESC
LIMIT 50;

-- Check current server status
SELECT version();
SELECT pg_postmaster_start_time();
SELECT pg_is_in_recovery();
```

## References
- Full SQLSTATE list: https://www.postgresql.org/docs/current/errcodes-appendix.html
- Error Reporting: https://www.postgresql.org/docs/current/runtime-config-error-handling.html
""",
    ),
    (
        "MySQL: Common Alerts and Troubleshooting Runbook",
        """\
# MySQL: Common Alerts and Troubleshooting Runbook

## High Thread Count / Too Many Connections

### Alert
- `max_connections` exceeded → `ERROR 1040: Too many connections`
- `Threads_connected` > 80% of `max_connections`

### Diagnosis
```sql
SHOW STATUS LIKE 'Threads%';
SHOW STATUS LIKE 'Max_used_connections';
SHOW VARIABLES LIKE 'max_connections';

-- Show current connections by host
SELECT host, COUNT(*) AS cnt FROM information_schema.processlist GROUP BY host;

-- Show full processlist
SHOW FULL PROCESSLIST;
```

### Remediation
```sql
-- Kill idle connections
SELECT CONCAT('KILL ', id, ';')
FROM information_schema.processlist
WHERE command = 'Sleep' AND time > 300;

-- Increase max_connections (also increase max_allowed_packet and innodb_buffer_pool)
SET GLOBAL max_connections = 500;
```

---

## InnoDB Deadlock

### Alert
- Application log: `Deadlock found when trying to get lock; try restarting transaction`
- MySQL error 1213

### Diagnosis
```sql
SHOW ENGINE INNODB STATUS\G
-- Look for "LATEST DETECTED DEADLOCK" section

-- Enable deadlock logging
SET GLOBAL innodb_print_all_deadlocks = ON;
```

### Remediation
1. Review and retry deadlocked transactions
2. Ensure consistent row access order across transactions
3. Use `SELECT ... FOR UPDATE` consistently
4. Keep transactions short

---

## Slow Query Alert

### Alert
- Slow query log entries with `Query_time` > threshold
- `Slow_queries` counter increasing rapidly

### Diagnosis
```sql
SHOW VARIABLES LIKE 'slow_query_log%';
SHOW VARIABLES LIKE 'long_query_time';
SHOW STATUS LIKE 'Slow_queries';

-- View slow queries from performance schema
SELECT digest_text, count_star, avg_timer_wait/1000000000 AS avg_sec,
       max_timer_wait/1000000000 AS max_sec
FROM performance_schema.events_statements_summary_by_digest
ORDER BY avg_timer_wait DESC
LIMIT 20;
```

### Remediation
```sql
-- Enable slow query log
SET GLOBAL slow_query_log = ON;
SET GLOBAL long_query_time = 1;
SET GLOBAL log_queries_not_using_indexes = ON;

-- Analyze a specific query
EXPLAIN FORMAT=JSON SELECT ...;
```

---

## InnoDB Buffer Pool Hit Rate Low

### Alert
- Buffer pool hit rate < 95%
- `Innodb_buffer_pool_reads` increasing

### Diagnosis
```sql
SHOW STATUS LIKE 'Innodb_buffer_pool_read%';

-- Calculate hit rate
SELECT
    (1 - (Innodb_buffer_pool_reads / Innodb_buffer_pool_read_requests)) * 100
        AS hit_rate_pct
FROM (
    SELECT
        VARIABLE_VALUE AS Innodb_buffer_pool_reads
    FROM performance_schema.global_status
    WHERE VARIABLE_NAME = 'Innodb_buffer_pool_reads'
) r,
(
    SELECT
        VARIABLE_VALUE AS Innodb_buffer_pool_read_requests
    FROM performance_schema.global_status
    WHERE VARIABLE_NAME = 'Innodb_buffer_pool_read_requests'
) rr;
```

### Remediation
- Increase `innodb_buffer_pool_size` to 70-80% of total RAM
- Identify large tables doing full scans and add indexes
- Use `innodb_buffer_pool_instances` > 1 for multi-core systems

---

## Replication Lag

### Alert
- `Seconds_Behind_Master` or `Seconds_Behind_Source` > threshold
- CloudWatch `ReplicaLag` metric firing

### Diagnosis
```sql
SHOW REPLICA STATUS\G  -- MySQL 8.0+
-- or
SHOW SLAVE STATUS\G    -- MySQL 5.7

-- Check for blocked replica threads
SHOW PROCESSLIST;
```

### Common Causes & Fixes
1. **Large transactions**: Enable `binlog_row_image = MINIMAL`
2. **Single-threaded replication**: Enable parallel replication:
   ```sql
   SET GLOBAL slave_parallel_workers = 4;
   SET GLOBAL slave_parallel_type = 'LOGICAL_CLOCK';
   ```
3. **Replica I/O bottleneck**: Use faster storage (gp3 with provisioned IOPS)

## References
- MySQL Error Codes: https://dev.mysql.com/doc/mysql-errors/8.0/en/server-error-reference.html
- InnoDB Monitoring: https://dev.mysql.com/doc/refman/8.0/en/innodb-monitors.html
- Replication: https://dev.mysql.com/doc/refman/8.0/en/replication.html
""",
    ),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def fetch_url(url: str, retries: int = 3, delay: float = 1.5) -> str | None:
    """Fetch URL content with retry logic. Returns None on failure."""
    headers = {
        "User-Agent": "Mozilla/5.0 (db-runbook-ingestion-bot/1.0)",
        "Accept": "text/plain, text/markdown, */*",
    }
    req = urllib.request.Request(url, headers=headers)
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                return response.read().decode("utf-8", errors="replace")
        except Exception as e:
            if attempt < retries - 1:
                print(f"    ⚠ Retry {attempt + 1}/{retries} for {url}: {e}")
                time.sleep(delay)
            else:
                print(f"    ✗ Failed to fetch {url}: {e}")
                return None
    return None


def clean_markdown(text: str) -> str:
    """Clean Hugo/MkDocs front matter and shortcode syntax from Markdown."""
    # Remove YAML/TOML front matter
    text = re.sub(r"^---\n.*?\n---\n", "", text, flags=re.DOTALL)
    text = re.sub(r"^\+\+\+\n.*?\n\+\+\+\n", "", text, flags=re.DOTALL)

    # Remove Hugo shortcodes like {{< sql "file.sql" >}}
    text = re.sub(r"\{\{<[^>]+>\}\}", "", text)
    text = re.sub(r"\{\{%[^%]+%\}\}", "", text)

    # Remove HTML comments
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)

    # Normalize excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


@dataclass
class DocumentSpec:
    title: str
    content: str
    source_type: str
    uri: str
    tags: str


# ---------------------------------------------------------------------------
# Main ingestion logic
# ---------------------------------------------------------------------------


def main() -> None:
    print("=" * 60)
    print("  DB Runbooks & Alerts Ingestion Pipeline")
    print("=" * 60)

    # ------------------------------------------------------------------
    # Bootstrap: embedding provider + pipeline
    # ------------------------------------------------------------------
    print("\n[1/4] Initializing embedding provider...")
    settings = Settings()
    if settings.embedding_provider == "gemini":
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is not set in environment or .env file.")
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
    print(f"      Model: {embedding_provider.model_name} "
          f"(dim={embedding_provider.dimension})")

    chunker = StructureAwareChunker()
    pipeline = IngestionPipeline(
        parsers=[MarkdownParser(), TextParser()],
        chunker=chunker,
        embedding_provider=embedding_provider,
    )

    # ------------------------------------------------------------------
    # Database setup
    # ------------------------------------------------------------------
    print("\n[2/4] Setting up database...")
    # Convert asyncpg to psycopg for synchronous engine creation
    db_url = settings.database_url.replace("postgresql+asyncpg", "postgresql+psycopg")
    engine = create_engine(db_url)

    # Ensure vector extension exists on Postgres
    if "postgresql" in db_url:
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()

    Base.metadata.create_all(engine)
    SessionFactory = sessionmaker(bind=engine)
    print(f"      DB URL: {db_url}")
    print("      Schema ready.")

    # ------------------------------------------------------------------
    # Collect all documents
    # ------------------------------------------------------------------
    print("\n[3/4] Fetching and preparing documents...")

    docs: list[DocumentSpec] = []

    # Fetch Qonto PostgreSQL runbooks
    print("\n  -> Qonto Framework: PostgreSQL Runbooks")
    for title, url, tags in PG_RUNBOOKS:
        print(f"    Fetching: {title}")
        raw = fetch_url(url)
        if raw:
            cleaned = clean_markdown(raw)
            if len(cleaned) > 100:
                docs.append(DocumentSpec(
                    title=title,
                    content=cleaned,
                    source_type="markdown",
                    uri=url,
                    tags=tags,
                ))
                print(f"    [OK] {len(cleaned)} chars")
            else:
                print("    [WARN] Content too short after cleaning, skipping")
        time.sleep(0.3)  # Rate limiting

    # Fetch Qonto RDS runbooks
    print("\n  -> Qonto Framework: AWS RDS Runbooks")
    for title, url, tags in RDS_RUNBOOKS:
        print(f"    Fetching: {title}")
        raw = fetch_url(url)
        if raw:
            cleaned = clean_markdown(raw)
            if len(cleaned) > 100:
                docs.append(DocumentSpec(
                    title=title,
                    content=cleaned,
                    source_type="markdown",
                    uri=url,
                    tags=tags,
                ))
                print(f"    [OK] {len(cleaned)} chars")
            else:
                print("    [WARN] Content too short after cleaning, skipping")
        time.sleep(0.3)

    # Add curated expert runbooks
    print("\n  -> Curated Expert Runbooks (local, hand-crafted)")
    for title, content in CURATED_RUNBOOKS:
        docs.append(DocumentSpec(
            title=title,
            content=content,
            source_type="markdown",
            uri=f"local://curated/{title.replace(' ', '_')}",
            tags="curated,runbook,database",
        ))
        print(f"    [OK] {title} ({len(content)} chars)")

    # ------------------------------------------------------------------
    # Ingest all documents
    # ------------------------------------------------------------------
    print(f"\n[4/4] Ingesting {len(docs)} documents into RAG pipeline...")
    print("-" * 60)

    ingested = 0
    skipped = 0
    failed = 0
    total_chunks = 0
    total_embeddings = 0

    start = datetime.now(UTC)

    with SessionFactory() as session:
        for i, doc in enumerate(docs, 1):
            print(f"  [{i:02d}/{len(docs):02d}] {doc.title[:55]:<55}", end="")
            try:
                result = pipeline.ingest(
                    session=session,
                    raw_content=doc.content,
                    source_type=doc.source_type,
                    title=doc.title,
                    uri=doc.uri,
                    metadata={
                        "tags": doc.tags,
                        "source": "db-runbook-ingestion",
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

    elapsed = (datetime.now(UTC) - start).total_seconds()

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("  INGESTION COMPLETE")
    print("=" * 60)
    print(f"  Documents ingested : {ingested}")
    print(f"  Duplicates skipped : {skipped}")
    print(f"  Failures           : {failed}")
    print(f"  Total chunks       : {total_chunks}")
    print(f"  Total embeddings   : {total_embeddings}")
    print(f"  Time elapsed       : {elapsed:.1f}s")
    print(f"  Database           : {db_url}")
    print("=" * 60)

    if ingested > 0:
        print("\n[SUCCESS] Knowledge base ready!")
        print("   Run manual_test.py and ask database-related questions like:")
        print('   - "What should I do when RDS disk space is critical?"')
        print('   - "How do I diagnose a PostgreSQL deadlock?"')
        print('   - "What causes replication lag and how to fix it?"')
        print('   - "How do I handle too many connections in PostgreSQL?"')
    elif failed > 0:
        print("\n[WARN] Some documents failed to ingest. Check errors above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
