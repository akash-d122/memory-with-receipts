"""SQL and Bash Command Sandbox Guardrails.

Inspects raw queries and command strings written by the agent against strict
regex-based whitelists and blocklists to prevent execution of dangerous modifications.
"""

from __future__ import annotations

import re


class SandboxValidationError(ValueError):
    """Raised when a command or query violates sandbox safety rules."""
    pass


# Strict SQL blocked keywords (case-insensitive)
BLOCKED_SQL_KEYWORDS = {
    "insert",
    "update",
    "delete",
    "drop",
    "alter",
    "truncate",
    "create",
    "replace",
    "grant",
    "revoke",
    "vacuum",  # vacuum should be manual or controlled, not run arbitrarily
    "copy",
    "into",
}

# Whitelisted safe shell command regexes
SAFE_BASH_PATTERNS = [
    # Disk space: e.g., 'df -h', 'df -h /var/lib/postgresql/data'
    re.compile(r"^df(\s+-[a-zA-Z0-9]+)?(\s+[\w/.-]+)?$"),
    # Memory: e.g., 'free -m', 'free -h', 'free -g'
    re.compile(r"^free(\s+-[a-zA-Z0-9]+)?$"),
    # Uptime / load average: 'uptime'
    re.compile(r"^uptime$"),
    # PostgreSQL ready check: e.g., 'pg_isready -U postgres -d memory_with_receipts'
    re.compile(r"^pg_isready(\s+-[a-zA-Z0-9]+(\s+\S+)?)*$"),
    # Safe process checks: e.g., 'ps aux', 'ps -ef | grep postgres'
    re.compile(r"^ps(\s+[a-zA-Z0-9-]+)?(\s*\|\s*grep\s+[\w.-]+)?$"),
    # Safe log checks: 'tail -n 100 /var/log/postgresql/postgresql.log'
    re.compile(r"^tail\s+-[nN]\s+\d+\s+[\w/.-]+$"),
    # Safe log search: 'grep -i error /var/log/postgresql/postgresql.log'
    re.compile(r"^grep\s+-[a-zA-Z\s\'\".-]+\s+[\w/.-]+$"),
]


def validate_sql(query: str) -> str:
    """Validate a SQL query to verify it is read-only.

    Args:
        query: Raw SQL query string.

    Returns:
        The validated query string.

    Raises:
        SandboxValidationError: If the query contains writing or dangerous keywords.
    """
    clean_query = query.strip()
    if not clean_query:
        raise SandboxValidationError("Query cannot be empty.")

    # Remove SQL comments to prevent keyword hiding
    # e.g., SELECT /* dangerous keyword */ ...
    no_comments = re.sub(r"/\*.*?\*/", "", clean_query, flags=re.DOTALL)
    no_comments = re.sub(r"--.*?\n", "\n", no_comments)

    # Extract all words/tokens
    tokens = re.findall(r"\b[a-zA-Z_]+\b", no_comments.lower())

    # Check against blocked keywords
    for token in tokens:
        if token in BLOCKED_SQL_KEYWORDS:
            raise SandboxValidationError(
                f"SQL query contains blocked dangerous keyword: '{token}'"
            )

    # Ensure query starts with a read-only keyword
    first_word_match = re.match(r"^\s*([a-zA-Z_]+)", no_comments)
    if not first_word_match:
        raise SandboxValidationError("Invalid SQL query format.")

    first_word = first_word_match.group(1).lower()
    allowed_start = {"select", "show", "explain", "with"}
    if first_word not in allowed_start:
        raise SandboxValidationError(
            f"SQL query starts with unauthorized command: '{first_word}'. "
            f"Only {sorted(allowed_start)} queries are permitted."
        )

    return clean_query


def validate_bash(command: str) -> str:
    """Validate a shell command string against the safe whitelist patterns.

    Args:
        command: Raw bash command string.

    Returns:
        The validated command string.

    Raises:
        SandboxValidationError: If the command is not on the whitelist.
    """
    clean_command = command.strip()
    if not clean_command:
        raise SandboxValidationError("Command cannot be empty.")

    # Block shell operators that can chain commands
    for separator in (";", "&&", "||", "\n", "`", "$("):
        if separator in clean_command:
            # Exception: allow 'ps | grep' pipeline since it's whitelisted as a single pattern
            if separator == "|" and re.match(r"^ps\s+.*\|\s*grep\s+.*$", clean_command):
                continue
            raise SandboxValidationError(
                f"Shell command contains blocked separator or execution token: '{separator}'"
            )

    # Check against whitelist patterns
    matched = False
    for pattern in SAFE_BASH_PATTERNS:
        if pattern.match(clean_command):
            matched = True
            break

    if not matched:
        raise SandboxValidationError(
            f"Shell command violates sandbox rules: '{clean_command}'. "
            "Only whitelisted read-only inspection commands (df, free, uptime, pg_isready, ps, tail/grep logs) are permitted."
        )

    return clean_command
