"""Unit tests for the SQL and Bash Sandbox Parser."""

from __future__ import annotations

import pytest

from memory_with_receipts.dbe_agent.sandbox import (
    SandboxValidationError,
    validate_bash,
    validate_sql,
)


def test_validate_sql_allows_read_only_queries():
    assert validate_sql("SELECT * FROM pg_stat_activity;") == "SELECT * FROM pg_stat_activity;"
    assert validate_sql("  EXPLAIN ANALYZE SELECT 1; ") == "EXPLAIN ANALYZE SELECT 1;"
    assert (
        validate_sql("WITH lag AS (SELECT 1) SELECT * FROM lag;")
        == "WITH lag AS (SELECT 1) SELECT * FROM lag;"
    )
    assert validate_sql("SHOW max_connections;") == "SHOW max_connections;"


def test_validate_sql_rejects_modifying_and_dangerous_queries():
    dangerous = [
        "DROP TABLE users;",
        "UPDATE pg_settings SET setting = 1000 WHERE name = 'max_connections';",
        "INSERT INTO source_records (title) VALUES ('test');",
        "DELETE FROM evidence_records;",
        "TRUNCATE TABLE memories CASCADE;",
        "ALTER TABLE chunks ADD COLUMN info text;",
        "SELECT * FROM users; DROP TABLE accounts;",  # chained statement
        "CREATE TABLE test (id int);",
        "SELECT /* dangerous comment */ 1; DROP TABLE users;",
    ]
    for sql in dangerous:
        with pytest.raises(SandboxValidationError):
            validate_sql(sql)


def test_validate_bash_allows_whitelisted_inspection_commands():
    allowed = [
        "df -h",
        "df -h /var/lib/postgresql/data",
        "free -m",
        "free -h",
        "uptime",
        "pg_isready",
        "pg_isready -U postgres -d memory_with_receipts",
        "ps aux",
        "ps -ef | grep postgres",
        "tail -n 100 /var/log/postgresql/postgresql.log",
        "grep -i error /var/log/postgresql/postgresql.log",
    ]
    for cmd in allowed:
        assert validate_bash(cmd) == cmd


def test_validate_bash_rejects_unauthorized_and_dangerous_commands():
    dangerous = [
        "rm -rf /",
        "curl http://malicious.site",
        "wget http://malicious.site",
        "df -h; rm -rf /",  # command injection
        "df -h && touch /dangerous",
        "uptime || poweroff",
        "cat /etc/passwd",
        "tail -n 100 /var/log/postgresql/postgresql.log > /tmp/hijack",  # redirection
        "ps aux & rm -rf /",
        "$(whoami)",
        "`whoami`",
    ]
    for cmd in dangerous:
        with pytest.raises(SandboxValidationError):
            validate_bash(cmd)
