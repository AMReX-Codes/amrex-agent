"""Shared status/severity labels for logs and feedback."""

SEVERITY_EMOJI = {
    "critical": "🛑",
    "error": "❌",
    "warning": "⚠️",
    "info": "ℹ️",
}

SEVERITY_TEXT = {
    "critical": "[CRITICAL]",
    "error": "[ERROR]",
    "warning": "[WARNING]",
    "info": "[INFO]",
}

STATUS_TEXT = {
    "success": "[SUCCESS]",
    "failed": "[FAILED]",
    "unstable": "[WARN]",
    "completed_with_warnings": "[WARN]",
    "incomplete": "[INCOMPLETE]",
    "no_log_file": "[NO_LOG]",
}

STATUS_EMOJI = {
    "success": "✅",
    "failed": "❌",
    "unstable": "⚠️",
    "completed_with_warnings": "⚠️",
    "incomplete": "🔄",
    "no_log_file": "❓",
}


def icon_for_severity(severity: str, use_emoji: bool = True) -> str:
    """Return a severity label (emoji or text)."""
    severity_key = (severity or "").lower()
    if use_emoji:
        return SEVERITY_EMOJI.get(severity_key, SEVERITY_EMOJI["info"])
    return SEVERITY_TEXT.get(severity_key, SEVERITY_TEXT["info"])


def status_label(status: str, use_emoji: bool = False) -> str:
    """Return a status label (text by default)."""
    status_key = (status or "").lower()
    if use_emoji:
        return STATUS_EMOJI.get(status_key, "❓")
    return STATUS_TEXT.get(status_key, "[UNKNOWN]")
