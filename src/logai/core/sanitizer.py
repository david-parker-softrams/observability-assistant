"""PII Sanitization layer for protecting sensitive data in logs."""

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SanitizationPattern:
    """Defines a pattern to detect and redact."""

    name: str
    pattern: re.Pattern[str]
    replacement: str
    enabled: bool = True


@dataclass
class SanitizationResult:
    """Result of sanitization with statistics."""

    sanitized_text: str
    redaction_count: int
    redactions: dict[str, int] = field(default_factory=dict)  # Pattern name -> count


class LogSanitizer:
    """Sanitizes log data before sending to LLM providers."""

    # Default patterns enabled by default
    DEFAULT_PATTERNS: list[SanitizationPattern] = [
        # Password in URL should run before email to avoid false matches
        SanitizationPattern(
            name="password_in_url",
            pattern=re.compile(r"://[^:]+:([^@]+)@"),
            replacement="://[user]:[PASSWORD_REDACTED]@",
        ),
        SanitizationPattern(
            name="email",
            pattern=re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
            replacement="[EMAIL_REDACTED]",
        ),
        SanitizationPattern(
            name="ipv4",
            pattern=re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"),
            replacement="[IP_REDACTED]",
        ),
        SanitizationPattern(
            name="ipv6",
            pattern=re.compile(r"([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}"),
            replacement="[IP_REDACTED]",
        ),
        SanitizationPattern(
            name="credit_card",
            pattern=re.compile(r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b"),
            replacement="[CC_REDACTED]",
        ),
        SanitizationPattern(
            name="ssn",
            pattern=re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
            replacement="[SSN_REDACTED]",
        ),
        SanitizationPattern(
            name="phone_us",
            pattern=re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"),
            replacement="[PHONE_REDACTED]",
        ),
        SanitizationPattern(
            name="aws_access_key",
            pattern=re.compile(r"AKIA[0-9A-Z]{16}"),
            replacement="[AWS_KEY_REDACTED]",
        ),
        SanitizationPattern(
            name="aws_secret_key",
            pattern=re.compile(r"(?i)aws.{0,20}secret.{0,20}['\"][0-9a-zA-Z/+=]{40}['\"]"),
            replacement="[AWS_SECRET_REDACTED]",
        ),
        SanitizationPattern(
            name="generic_api_key",
            pattern=re.compile(
                r"(?i)(api[_\s-]?key|apikey|api[_\s-]?secret)[:\s=\"']*[\"']?([a-zA-Z0-9_-]{20,})[\"']?"
            ),
            replacement=r"\1 [API_KEY_REDACTED]",
        ),
        SanitizationPattern(
            name="bearer_token",
            pattern=re.compile(r"(?i)bearer\s+[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+"),
            replacement="[TOKEN_REDACTED]",
        ),
        SanitizationPattern(
            name="private_key",
            pattern=re.compile(r"-----BEGIN\s+(RSA|DSA|EC|OPENSSH)?\s*PRIVATE KEY-----"),
            replacement="[PRIVATE_KEY_REDACTED]",
        ),
    ]

    def __init__(
        self, enabled: bool = True, custom_patterns: list[SanitizationPattern] | None = None
    ):
        """
        Initialize sanitizer.

        Args:
            enabled: Whether sanitization is enabled
            custom_patterns: Additional patterns to use beyond defaults
        """
        self.enabled = enabled
        self.patterns = self.DEFAULT_PATTERNS.copy()
        if custom_patterns:
            self.patterns.extend(custom_patterns)

    def sanitize(self, text: str) -> SanitizationResult:
        """
        Sanitize text, removing PII and sensitive data.

        Args:
            text: Text to sanitize

        Returns:
            SanitizationResult with sanitized text and statistics
        """
        if not self.enabled:
            return SanitizationResult(
                sanitized_text=text,
                redaction_count=0,
                redactions={},
            )

        redactions: dict[str, int] = {}
        result = text

        for pattern in self.patterns:
            if not pattern.enabled:
                continue

            matches = pattern.pattern.findall(result)
            if matches:
                count = len(matches) if isinstance(matches, list) else 1
                redactions[pattern.name] = redactions.get(pattern.name, 0) + count
                result = pattern.pattern.sub(pattern.replacement, result)

        total_redactions = sum(redactions.values())

        return SanitizationResult(
            sanitized_text=result,
            redaction_count=total_redactions,
            redactions=redactions,
        )

    def sanitize_log_events(
        self, events: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], dict[str, int]]:
        """
        Sanitize a list of log events.

        Args:
            events: List of log event dictionaries

        Returns:
            Tuple of (sanitized events, aggregated redaction stats)
        """
        if not self.enabled:
            return events, {}

        sanitized_events = []
        total_redactions: dict[str, int] = {}

        for event in events:
            sanitized_event = event.copy()

            # Sanitize the message field if present
            if "message" in sanitized_event and isinstance(sanitized_event["message"], str):
                result = self.sanitize(sanitized_event["message"])
                sanitized_event["message"] = result.sanitized_text

                # Aggregate redaction statistics
                for pattern_name, count in result.redactions.items():
                    total_redactions[pattern_name] = total_redactions.get(pattern_name, 0) + count

            sanitized_events.append(sanitized_event)

        return sanitized_events, total_redactions

    def sanitize_dict(
        self, data: dict[str, Any], keys_to_sanitize: list[str] | None = None
    ) -> tuple[dict[str, Any], dict[str, int]]:
        """
        Sanitize specific keys in a dictionary.

        Args:
            data: Dictionary to sanitize
            keys_to_sanitize: List of keys to sanitize (default: all string values)

        Returns:
            Tuple of (sanitized dict, aggregated redaction stats)
        """
        if not self.enabled:
            return data, {}

        sanitized_data = data.copy()
        total_redactions: dict[str, int] = {}

        keys = keys_to_sanitize if keys_to_sanitize else data.keys()

        for key in keys:
            if key in sanitized_data and isinstance(sanitized_data[key], str):
                result = self.sanitize(sanitized_data[key])
                sanitized_data[key] = result.sanitized_text

                # Aggregate redaction statistics
                for pattern_name, count in result.redactions.items():
                    total_redactions[pattern_name] = total_redactions.get(pattern_name, 0) + count

        return sanitized_data, total_redactions

    def get_redaction_summary(self, redactions: dict[str, int]) -> str:
        """
        Generate a human-readable summary of redactions.

        Args:
            redactions: Dictionary of pattern name -> count

        Returns:
            Human-readable summary string
        """
        if not redactions:
            return "No sensitive data redacted"

        parts = []
        for pattern_name, count in sorted(redactions.items()):
            # Convert pattern name to readable format
            readable_name = pattern_name.replace("_", " ").title()
            parts.append(f"{count} {readable_name}")

        return f"Redacted: {', '.join(parts)}"
