import logging

import anthropic

from config import settings

logger = logging.getLogger(__name__)

TRIAGE_PROMPT = """You are an SRE assistant. An alert has fired in production.

Alert: {alert_name}
Severity: {severity}
Affected service: {service}
Firing since: {firing_time}

Recent metrics (last 30 minutes):
- Error rate: {error_rate}
- p99 latency: {p99_latency}
- Pod restarts: {restart_count}

Recent error logs:
{log_lines}

Based on this data:
1. What is the most likely root cause?
2. What is the immediate remediation step?
3. What follow-up investigation is recommended?

Be concise. Use bullet points. Flag if you need more data."""


async def triage_alert(
    alert_name: str,
    severity: str,
    service: str,
    firing_time: str,
    error_rate: str,
    p99_latency: str,
    restart_count: str,
    log_lines: str,
) -> dict[str, str]:
    """Call Claude API to triage an alert and return structured analysis."""
    prompt = TRIAGE_PROMPT.format(
        alert_name=alert_name,
        severity=severity,
        service=service,
        firing_time=firing_time,
        error_rate=error_rate,
        p99_latency=p99_latency,
        restart_count=restart_count,
        log_lines=log_lines,
    )

    try:
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        message = await client.messages.create(
            model=settings.claude_model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        response_text = message.content[0].text

        # Parse the response into root_cause and recommendation
        root_cause, recommendation = _parse_triage_response(response_text)

        return {
            "root_cause": root_cause,
            "recommendation": recommendation,
            "full_response": response_text,
        }
    except Exception as e:
        logger.error("Claude API call failed: %s", e)
        return {
            "root_cause": f"Triage failed: {e}",
            "recommendation": "Manual investigation required. Claude API call failed.",
            "full_response": "",
        }


def _parse_triage_response(text: str) -> tuple[str, str]:
    """Split Claude's response into root cause and recommendation sections."""
    sections = text.split("\n\n")

    root_cause = ""
    recommendation = ""
    current_section = ""

    for line in text.split("\n"):
        lower = line.lower().strip()
        if "root cause" in lower or "1." in lower[:3]:
            current_section = "root_cause"
        elif "remediation" in lower or "2." in lower[:3]:
            current_section = "recommendation"
        elif "follow-up" in lower or "investigation" in lower or "3." in lower[:3]:
            current_section = "recommendation"

        if current_section == "root_cause":
            root_cause += line + "\n"
        elif current_section == "recommendation":
            recommendation += line + "\n"

    # Fallback: if parsing fails, put everything in root_cause
    if not root_cause.strip():
        root_cause = text
    if not recommendation.strip():
        recommendation = "See full triage response for details."

    return root_cause.strip(), recommendation.strip()
