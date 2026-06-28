"""DBE Diagnostic Agent.

Orchestrates the ReAct diagnostic loop, parsing action tokens, executing tools,
logging step details, and rendering the final audited RCA report.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from memory_with_receipts.core.exceptions import GenerationError
from memory_with_receipts.core.logging import get_logger
from memory_with_receipts.llm.base import BaseLLMProvider
from memory_with_receipts.dbe_agent.tools import execute_bash, execute_sql, query_pmm_metrics

logger = get_logger(__name__)


@dataclass
class DiagnosticStep:
    """Represents a single step in the ReAct diagnostic loop."""
    step_number: int
    thought: str
    action_tool: str | None = None
    action_argument: Any = None
    observation: str | None = None


@dataclass
class DiagnosticReport:
    """The final diagnosis output compiled by the agent."""
    incident_title: str
    steps: list[DiagnosticStep] = field(default_factory=list)
    rca_report: str = ""
    is_successful: bool = True
    error_message: str | None = None


SYSTEM_PROMPT = """You are an expert Database Engineer (DBE) diagnosing operational alerts.
You are given a query or incident description. Your goal is to run diagnostics using tools, find the root cause (RCA), and provide recommendations.

You have access to these safe, read-only tools:
1. execute_sql(query="SELECT ..."): Run read-only queries against the Postgres database.
2. execute_bash(command="df -h"): Execute whitelisted read-only inspection commands (df, free, uptime, pg_isready, ps, tail/grep logs).
3. query_pmm_metrics(metric_name="cpu_utilization", duration_minutes=15): Fetch timeseries metrics data.

Strict Guidelines:
- You must ONLY execute read-only queries or whitelisted inspect commands. Modifying commands (INSERT, UPDATE, DROP, rm, etc.) are blocked by a strict sandbox parser and will throw validation errors.
- Analyze query result tables and command outputs carefully to diagnose lock contention, CPU spikes, disk fullness, WAL issues, connection exhaustion, etc.
- Keep diagnostic sessions concise. Use tool calls to find factual evidence.

For each turn, format your thoughts and tool calls exactly as follows:
Thought: <your reason for checking next, analyzing previous findings>
Action: <tool_name>(<arguments>)

Once you have gathered sufficient evidence to form a definitive Root Cause Analysis (RCA), output exactly:
Thought: <final reasoning summary>
RCA Report:
# [Incident Title or Summary]
## Root Cause Analysis
<provide detailed diagnosis with data points from your tool outputs>
## Preventative Recommendations
<provide short-term and long-term actions to prevent recurrence>
## Remediation Steps
<provide exact safe SQL queries or CLI commands SREs should run to fix the active issue>
"""


def parse_action(text: str) -> tuple[str, Any] | None:
    """Parse Action tokens from LLM completion text.

    Supported patterns:
      Action: execute_sql("SELECT ...")
      Action: execute_bash(command="df -h")
      Action: query_pmm_metrics("cpu", 15)
    """
    match = re.search(r"Action:\s*(\w+)\(", text)
    if not match:
        return None

    tool_name = match.group(1)
    start_idx = match.end()

    # Track matching parentheses to find the correct closing parenthesis
    depth = 1
    end_idx = start_idx
    while depth > 0 and end_idx < len(text):
        char = text[end_idx]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        end_idx += 1

    if depth > 0:
        return None

    arg_content = text[start_idx:end_idx-1].strip()

    # Clean query= or command= named parameter labels
    named_arg_match = re.match(r"^(?:query|command|metric_name)\s*=\s*(.*)$", arg_content, re.DOTALL)
    if named_arg_match:
        arg_content = named_arg_match.group(1).strip()

    # Strip quote wraps
    for quote in ('"""', "'''", '"', "'"):
        if arg_content.startswith(quote) and arg_content.endswith(quote):
            arg_content = arg_content[len(quote):-len(quote)].strip()
            break

    # Specific parameter extraction for multi-param tools
    if tool_name == "query_pmm_metrics":
        # Positional split
        parts = [p.strip().strip("'\"") for p in arg_content.split(",")]
        metric_name = parts[0] if parts else "cpu_utilization"
        duration_minutes = 15
        if len(parts) > 1:
            try:
                duration_minutes = int(parts[1])
            except ValueError:
                pass
        return tool_name, (metric_name, duration_minutes)

    return tool_name, arg_content


def extract_thought(text: str) -> str:
    """Extract content following the 'Thought:' token, up to 'Action:' or 'RCA Report:'."""
    match = re.search(r"Thought:\s*(.*?)(?=\bAction:|\bRCA Report:|$)", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    # Fallback to returning the first line or raw block if not formatted cleanly
    return text.split("\n")[0].strip()


class DBEDiagnosticAgent:
    """Orchestrates ReAct DBE diagnostic tool calling iterations."""

    def __init__(self, llm_provider: BaseLLMProvider) -> None:
        self._llm_provider = llm_provider

    async def diagnose(
        self,
        session: Session,
        query: str,
        max_steps: int = 5,
        runbook_context: list[str] | None = None,
    ) -> DiagnosticReport:
        """Run the Google ADK tools calling diagnostics loop to generate an RCA report.

        Args:
            session: SQLAlchemy DB session.
            query: User search query or incident alert name.
            max_steps: Maximum loop steps to prevent runaway calls.
            runbook_context: Optional SRE runbook chunks to inject as context.

        Returns:
            DiagnosticReport containing steps execution console logs and the RCA.
        """
        logger.info("dbe_diagnose_started", query=query, max_steps=max_steps)

        system_prompt = SYSTEM_PROMPT
        if runbook_context:
            context_str = "\n".join(f"- {chunk}" for chunk in runbook_context)
            system_prompt += (
                f"\n\nRelevant Runbook Knowledge:\n"
                f"---\n"
                f"{context_str}\n"
                f"---\n"
            )

        steps: list[DiagnosticStep] = []
        report = DiagnosticReport(incident_title=query, steps=steps)

        # Handle Mock LLM Provider
        if getattr(self._llm_provider, "provider_name", None) == "mock":
            # Simulate ADK runner execution using mock LLM response sequence
            events = []
            conversation_history = [
                f"System Prompt:\n{system_prompt}",
                f"User Incident Query: {query}",
            ]
            from unittest.mock import MagicMock
            for step_idx in range(1, max_steps + 1):
                prompt = "\n\n".join(conversation_history) + "\n\nAssistant:"
                try:
                    res = self._llm_provider.generate(prompt)
                    response_text = res.answer.strip()
                except Exception as exc:
                    report.is_successful = False
                    report.error_message = f"LLM generation failed: {exc}"
                    return report

                conversation_history.append(response_text)
                thought = extract_thought(response_text)
                action_info = parse_action(response_text)

                # Create Mock Turn Update Event
                turn_update = MagicMock()
                turn_update.__class__.__name__ = "AgentTurnUpdateEvent"
                part = MagicMock()
                part.text = response_text
                part.function_call = None
                content = MagicMock()
                content.parts = [part]
                candidate = MagicMock()
                candidate.content = content
                turn_update.model_response.candidates = [candidate]
                events.append(turn_update)

                if "RCA Report:" in response_text:
                    turn_completed = MagicMock()
                    turn_completed.__class__.__name__ = "AgentTurnCompletedEvent"
                    turn_completed.final_response.candidates = [candidate]
                    events.append(turn_completed)
                    break

                if not action_info:
                    turn_completed = MagicMock()
                    turn_completed.__class__.__name__ = "AgentTurnCompletedEvent"
                    turn_completed.final_response.candidates = [candidate]
                    events.append(turn_completed)
                    break

                tool_name, tool_arg = action_info
                
                # Create Tool Call Start Event
                tool_start = MagicMock()
                tool_start.__class__.__name__ = "ToolCallStartedEvent"
                tool_start.tool_name = tool_name
                tool_start.args = tool_arg
                events.append(tool_start)

                # Execute tool
                if tool_name == "execute_sql":
                    observation = execute_sql(session, str(tool_arg))
                elif tool_name == "execute_bash":
                    observation = execute_bash(str(tool_arg))
                elif tool_name == "query_pmm_metrics":
                    metric_name, duration = tool_arg
                    observation = query_pmm_metrics(metric_name, duration)
                else:
                    observation = f"ERROR: Unknown tool name: '{tool_name}'."

                # Create Tool Call Completed Event
                tool_completed = MagicMock()
                tool_completed.__class__.__name__ = "ToolCallCompletedEvent"
                tool_completed.tool_name = tool_name
                tool_completed.response.response = {"result": observation}
                events.append(tool_completed)

                conversation_history.append(f"Observation: {observation}")
        else:
            # Production: Run using Google ADK Agent and InMemoryRunner
            from google.adk.agents import Agent
            from google.adk.runners import InMemoryRunner
            from google.adk.tools import FunctionTool

            # Bind Session dependency to the SQL tool
            def run_sql(query: str) -> str:
                """Execute a read-only SQL query against PostgreSQL."""
                return execute_sql(session, query)

            sql_tool = FunctionTool(run_sql)
            bash_tool = FunctionTool(execute_bash)
            pmm_tool = FunctionTool(query_pmm_metrics)

            adk_agent = Agent(
                name="dbe_diagnostic_agent",
                instruction=system_prompt,
                tools=[sql_tool, bash_tool, pmm_tool]
            )
            runner = InMemoryRunner(agent=adk_agent)
            try:
                events = await runner.run_debug(query)
            except Exception as exc:
                logger.exception("dbe_diagnose_adk_failed")
                report.is_successful = False
                report.error_message = f"ADK execution failed: {exc}"
                return report

        # Reconstruct the ReAct DiagnosticReport trace from runner events
        current_step_num = 1
        current_thought = ""

        for e in events:
            event_name = type(e).__name__
            if event_name == "AgentTurnUpdateEvent":
                candidates = getattr(e.model_response, "candidates", [])
                if candidates:
                    content = getattr(candidates[0], "content", None)
                    if content and content.parts:
                        for part in content.parts:
                            if part.text:
                                current_thought = part.text.strip()
            elif event_name == "ToolCallStartedEvent":
                step = DiagnosticStep(
                    step_number=current_step_num,
                    thought=current_thought or "Invoking diagnostic tool.",
                    action_tool=e.tool_name,
                    action_argument=e.args,
                )
                steps.append(step)
                current_step_num += 1
                current_thought = ""
            elif event_name == "ToolCallCompletedEvent":
                if steps and steps[-1].action_tool == e.tool_name:
                    resp_obj = getattr(e.response, "response", None)
                    if isinstance(resp_obj, dict) and "result" in resp_obj:
                        observation = str(resp_obj["result"])
                    else:
                        observation = str(e.response)
                    steps[-1].observation = observation
            elif event_name == "AgentTurnCompletedEvent":
                candidates = getattr(e.final_response, "candidates", [])
                if candidates:
                    content = getattr(candidates[0], "content", None)
                    if content and content.parts:
                        final_text = "".join(part.text for part in content.parts if part.text)
                        if "RCA Report:" in final_text:
                            rca_split = final_text.split("RCA Report:", 1)
                            report.rca_report = rca_split[1].strip()
                            steps.append(
                                DiagnosticStep(
                                    step_number=current_step_num,
                                    thought=rca_split[0].strip() or "Compiling final diagnostic report.",
                                )
                            )
                        else:
                            report.rca_report = final_text.strip()
                            steps.append(
                                DiagnosticStep(
                                    step_number=current_step_num,
                                    thought=current_thought or "Concluded diagnostics.",
                                )
                            )

        if not report.rca_report:
            report.is_successful = False
            report.error_message = "Agent reached maximum diagnostic steps without outputting an RCA Report."

        return report
