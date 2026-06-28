"""Notification dispatchers for Slack and Google Chat.

Sends the finalized diagnostic RCA report to Slack and Google Chat via
standard incoming webhooks.
"""

from __future__ import annotations

import json
import urllib.request
from urllib.error import URLError

from memory_with_receipts.core.logging import get_logger

logger = get_logger(__name__)


def send_slack_notification(webhook_url: str, text_content: str, incident_title: str) -> bool:
    """Send a formatted SRE alert diagnostic report to Slack.

    Args:
        webhook_url: Slack incoming webhook URL.
        text_content: Markdown text body of the RCA.
        incident_title: Title of the incident.

    Returns:
        True if successfully sent, False otherwise.
    """
    if not webhook_url:
        logger.debug("slack_notification_skipped_no_webhook")
        return False

    # Standard Slack payload structure
    payload = {
        "text": f"🚨 *Aegis DBE Agent Diagnostics: {incident_title}*",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"🚨 *Aegis DBE Agent Diagnostics: {incident_title}*",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": text_content[:3000],  # Slack text block limit is 3000 chars
                },
            },
        ],
    }

    try:
        req = urllib.request.Request(
            webhook_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as res:
            if res.status in (200, 201):
                logger.info("slack_notification_sent_successfully")
                return True
            logger.warning("slack_notification_failed_status", status_code=res.status)
    except URLError as err:
        logger.warning("slack_notification_network_error", error=str(err))
    except Exception as exc:
        logger.exception("slack_notification_unexpected_error", error=str(exc))

    return False


def send_gchat_notification(webhook_url: str, text_content: str, incident_title: str) -> bool:
    """Send a formatted SRE alert diagnostic report to Google Chat.

    Args:
        webhook_url: Google Chat incoming webhook URL.
        text_content: Markdown text body of the RCA.
        incident_title: Title of the incident.

    Returns:
        True if successfully sent, False otherwise.
    """
    if not webhook_url:
        logger.debug("gchat_notification_skipped_no_webhook")
        return False

    # Google Chat payload structure
    payload = {
        "text": f"🚨 *Aegis DBE Agent Diagnostics: {incident_title}*\n\n{text_content}",
    }

    try:
        req = urllib.request.Request(
            webhook_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=UTF-8"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as res:
            if res.status in (200, 201):
                logger.info("gchat_notification_sent_successfully")
                return True
            logger.warning("gchat_notification_failed_status", status_code=res.status)
    except URLError as err:
        logger.warning("gchat_notification_network_error", error=str(err))
    except Exception as exc:
        logger.exception("gchat_notification_unexpected_error", error=str(exc))

    return False
