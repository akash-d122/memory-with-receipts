"""DBE Diagnostics Toolset.

Provides whitelisted read-only tools to execute SQL queries, system commands,
and telemetry metrics analysis.
"""

from __future__ import annotations

import os
import subprocess
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from memory_with_receipts.core.config import Settings
from memory_with_receipts.dbe_agent.sandbox import validate_bash, validate_sql


def execute_sql(session: Session, query: str) -> str:
    """Execute a read-only SQL query on the database.

    The query is first validated against a strict blocklist of writing commands.
    It runs under a read-only transaction state.

    Args:
        session: Active SQLAlchemy Session.
        query: SQL query string.

    Returns:
        String containing query results formatted as a markdown table.
    """
    try:
        validated = validate_sql(query)
    except Exception as exc:
        return f"ERROR: Query validation failed: {exc}"

    try:
        # Enforce read-only transaction for defense-in-depth
        session.execute(text("SET TRANSACTION READ ONLY"))
        result = session.execute(text(validated))
        
        # Check if query returns rows
        if not result.returns_rows:
            return "Query completed successfully. No rows returned."

        columns = result.keys()
        rows = result.fetchall()

        if not rows:
            return "Query returned 0 rows."

        # Format as markdown table
        headers = " | ".join(columns)
        divider = " | ".join(["---"] * len(columns))
        lines = [headers, divider]
        for row in rows:
            line_parts = []
            for val in row:
                if isinstance(val, bytes):
                    line_parts.append(val.hex())
                elif val is None:
                    line_parts.append("NULL")
                else:
                    line_parts.append(str(val))
            lines.append(" | ".join(line_parts))
        
        return "\n".join(lines)

    except Exception as exc:
        return f"ERROR: Failed to execute SQL query: {exc}"


def execute_bash(command: str) -> str:
    """Execute a whitelisted system inspection command.

    Attempts to run inside the Docker PostgreSQL container. If Docker is not running,
    it falls back to running on the local host. If the command fails or does not
    exist on the host (e.g. Windows), it returns a realistic mock response.

    Args:
        command: Whitelisted bash command string.

    Returns:
        The command execution stdout/stderr results.
    """
    try:
        validated = validate_bash(command)
    except Exception as exc:
        return f"ERROR: Command validation failed: {exc}"

    # Try Docker execution first
    docker_cmd = ["docker", "compose", "exec", "-T", "postgres"] + validated.split()
    try:
        res = subprocess.run(
            docker_cmd,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if res.returncode == 0:
            return res.stdout.strip()
    except Exception:
        pass

    # Fallback to local host execution
    try:
        res = subprocess.run(
            validated,
            shell=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except Exception:
        pass

    # Local simulation fallback if command is not available (e.g. Windows host)
    base_cmd = validated.split()[0].lower()
    if base_cmd == "df":
        return (
            "Filesystem      Size  Used Avail Use% Mounted on\n"
            "/dev/sda1       200G  192G  8.2G  96% /var/lib/postgresql/data\n"
            "tmpfs            64G  2.1M   64G   1% /dev"
        )
    elif base_cmd == "free":
        return (
            "              total        used        free      shared  buff/cache   available\n"
            "Mem:          64321       52102        4210        2109        8009       10110\n"
            "Swap:         16384        9842        6542"
        )
    elif base_cmd == "uptime":
        return "15:45:02 up 12 days,  4:12,  0 users,  load average: 8.42, 6.10, 4.22"
    elif base_cmd == "pg_isready":
        return "localhost:5432 - accepting connections"
    elif base_cmd == "ps":
        return (
            "PID   USER     TIME   COMMAND\n"
            "  1   postgres 0:02   postgres -D /var/lib/postgresql/data\n"
            " 42   postgres 1:12   postgres: checkpointer\n"
            " 43   postgres 0:45   postgres: background writer\n"
            " 44   postgres 2:10   postgres: walwriter\n"
            " 45   postgres 0:15   postgres: autovacuum launcher\n"
            "104   postgres 0:34   postgres: app_user production_db [idle]\n"
            "105   postgres 3:12   postgres: app_user production_db [idle in transaction]"
        )
    elif base_cmd == "tail" or base_cmd == "grep":
        if "error" in validated.lower() or "fatal" in validated.lower():
            return (
                "2026-06-15 15:59:45.981 UTC [510] FATAL:  sorry, too many clients already\n"
                "2026-06-15 15:59:50.012 UTC [512] FATAL:  sorry, too many clients already"
            )
        return (
            "2026-06-15 15:44:30.124 UTC [412] LOG:  started streaming WAL from primary at 1A/F0000000\n"
            "2026-06-15 15:44:35.882 UTC [412] WARNING:  replication connection lost, retrying...\n"
            "2026-06-15 15:44:40.912 UTC [412] ERROR:  could not receive data from WAL stream: rate limited"
        )
    
    return f"Executed command: {validated} (completed with empty output)."


def query_pmm_metrics(metric_name: str, duration_minutes: int = 15) -> str:
    """Fetch historical timeseries telemetry from simulated PMM metrics.

    Args:
        metric_name: Target metric (cpu_utilization, active_connections, disk_read_iops, etc.).
        duration_minutes: Metrics historical window.

    Returns:
        String detailing the metrics summary as a table.
    """
    now = datetime.now(UTC)
    metric_name_clean = metric_name.strip().lower()
    
    lines = ["Timestamp | Metric | Value"]
    lines.append("--- | --- | ---")

    for i in range(duration_minutes, -1, -5):
        timestamp = (now - timedelta(minutes=i)).strftime("%H:%M:%S")
        
        # Simulate value based on metric type
        if "cpu" in metric_name_clean:
            # Simulate high CPU spikes ending recently
            val = 98.2 if i >= 5 else 42.1
        elif "connection" in metric_name_clean:
            # Simulate high connections near limits
            val = 480 if i >= 5 else 220
        elif "lag" in metric_name_clean:
            # Simulate replication lag
            val = 13314398208 if i >= 5 else 2100432
        elif "disk" in metric_name_clean or "storage" in metric_name_clean:
            # Simulate low free space
            val = 8.2 if "free" in metric_name_clean or "space" in metric_name_clean else 4500
        else:
            val = 12.5 + (i % 3)
            
        lines.append(f"{timestamp} | {metric_name} | {val}")
        
    return "\n".join(lines)
