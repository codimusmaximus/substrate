"""Events domain - pure logic functions for condition matching."""
import re
from typing import Any


def matches_conditions(event: dict, conditions: dict) -> bool:
    """
    Check if an event matches all conditions in a rule.

    Supported conditions:
    - from_contains, from_equals
    - to_contains, to_equals
    - subject_contains, subject_equals, subject_matches (regex)
    - body_contains
    - has_attachment
    - event_type_equals

    All conditions must match (AND logic).
    """
    for condition_type, condition_value in conditions.items():
        if not _check_condition(event, condition_type, condition_value):
            return False
    return True


def _check_condition(event: dict, condition_type: str, value: Any) -> bool:
    """Check a single condition against an event."""
    # Email from conditions
    if condition_type == "from_contains":
        return _contains(event.get("email_from", ""), value)
    if condition_type == "from_equals":
        return _equals(event.get("email_from", ""), value)

    # Email to conditions
    if condition_type == "to_contains":
        return _contains(event.get("email_to", ""), value)
    if condition_type == "to_equals":
        return _equals(event.get("email_to", ""), value)

    # Subject conditions
    if condition_type == "subject_contains":
        return _contains(event.get("email_subject", ""), value)
    if condition_type == "subject_equals":
        return _equals(event.get("email_subject", ""), value)
    if condition_type == "subject_matches":
        return _regex_match(event.get("email_subject", ""), value)

    # Body conditions
    if condition_type == "body_contains":
        return _contains(event.get("email_body", ""), value)

    # Attachment condition
    if condition_type == "has_attachment":
        payload = event.get("payload", {})
        has_att = bool(payload.get("attachments"))
        return has_att == value

    # Event type condition
    if condition_type == "event_type_equals":
        return event.get("event_type") == value

    # Source condition
    if condition_type == "source_equals":
        return event.get("source") == value

    # Unknown condition type - fail safe
    return False


def _contains(text: str, substring: str) -> bool:
    """Case-insensitive contains check."""
    if not text or not substring:
        return False
    return substring.lower() in text.lower()


def _equals(text: str, value: str) -> bool:
    """Case-insensitive equals check."""
    if not text or not value:
        return text == value
    return text.lower() == value.lower()


def _regex_match(text: str, pattern: str) -> bool:
    """Regex match (case-insensitive)."""
    if not text or not pattern:
        return False
    try:
        return bool(re.search(pattern, text, re.IGNORECASE))
    except re.error:
        return False


def event_summary(event: dict) -> str:
    """Generate a short summary of an event for display."""
    source = event.get("source", "unknown")
    event_type = event.get("event_type", "unknown")

    if source == "email":
        sender = event.get("email_from", "unknown")
        subject = event.get("email_subject", "no subject")
        return f"Email from {sender}: {subject[:50]}"

    return f"{source}/{event_type}"
