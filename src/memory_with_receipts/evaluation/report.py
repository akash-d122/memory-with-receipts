"""Text/Markdown report generator for evaluation results.

generate_text_report(report) → str  produces a human-readable
summary suitable for printing to CI logs or saving as a .md file.
"""

from __future__ import annotations

from memory_with_receipts.evaluation.schemas import EvalReport


def generate_text_report(report: EvalReport) -> str:
    """Generate a human-readable Markdown evaluation report.

    Args:
        report: EvalReport produced by EvalRunner.run_all().

    Returns:
        Formatted Markdown string with aggregate stats and per-case details.
    """
    lines: list[str] = []

    # Header
    lines.append("# Evaluation Report")
    lines.append("")
    if report.dataset_path:
        lines.append(f"**Dataset**: `{report.dataset_path}`")
    lines.append(f"**Generated**: {report.generated_at}")
    lines.append("")

    # Aggregate summary
    status_icon = "✅" if report.failed == 0 else "❌"
    lines.append(f"## Summary {status_icon}")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Total cases | {report.total_cases} |")
    lines.append(f"| Passed | {report.passed} |")
    lines.append(f"| Failed | {report.failed} |")
    lines.append(f"| **Pass rate** | **{report.pass_rate:.1%}** |")
    lines.append("")

    # Per-metric pass rates
    if report.per_metric_pass_rate:
        lines.append("## Per-Metric Pass Rate")
        lines.append("")
        lines.append("| Metric | Pass Rate |")
        lines.append("|--------|-----------|")
        for name, rate in sorted(report.per_metric_pass_rate.items()):
            icon = "✅" if rate == 1.0 else ("⚠️" if rate >= 0.5 else "❌")
            lines.append(f"| {name} | {rate:.1%} {icon} |")
        lines.append("")

    # Per-case breakdown
    lines.append("## Case Details")
    lines.append("")
    for cr in report.cases:
        status = "✅ PASS" if cr.passed else "❌ FAIL"
        lines.append(f"### `{cr.case_id}` — {status}")
        lines.append(f"**Query**: {cr.query}")
        lines.append(f"**is_insufficient**: {cr.is_insufficient}")
        lines.append(f"**Answer** (truncated): {cr.answer[:200]}...")
        lines.append("")
        lines.append("**Metrics**:")
        for m in cr.metrics:
            m_icon = "✅" if m.passed else "❌"
            lines.append(
                f"- {m_icon} `{m.name}` — score={m.score:.3f} — {m.detail}"
            )
        lines.append("")

    return "\n".join(lines)
