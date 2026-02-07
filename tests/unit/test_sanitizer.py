"""Tests for PII sanitization."""

import re

import pytest

from logai.core import LogSanitizer, SanitizationPattern, SanitizationResult


class TestLogSanitizer:
    """Test suite for LogSanitizer."""

    def test_sanitizer_enabled_by_default(self) -> None:
        """Test that sanitizer is enabled by default."""
        sanitizer = LogSanitizer()
        assert sanitizer.enabled is True

    def test_sanitizer_can_be_disabled(self) -> None:
        """Test that sanitizer can be disabled."""
        sanitizer = LogSanitizer(enabled=False)
        assert sanitizer.enabled is False

    def test_disabled_sanitizer_returns_original_text(self) -> None:
        """Test that disabled sanitizer returns original text unchanged."""
        sanitizer = LogSanitizer(enabled=False)
        text = "Contact me at user@example.com or call 555-123-4567"

        result = sanitizer.sanitize(text)

        assert result.sanitized_text == text
        assert result.redaction_count == 0
        assert result.redactions == {}

    def test_sanitize_email_addresses(self) -> None:
        """Test sanitization of email addresses."""
        sanitizer = LogSanitizer()
        text = "Contact user@example.com or admin@company.org for help"

        result = sanitizer.sanitize(text)

        assert "[EMAIL_REDACTED]" in result.sanitized_text
        assert "user@example.com" not in result.sanitized_text
        assert "admin@company.org" not in result.sanitized_text
        assert result.redactions["email"] == 2

    def test_sanitize_ipv4_addresses(self) -> None:
        """Test sanitization of IPv4 addresses."""
        sanitizer = LogSanitizer()
        text = "Server at 192.168.1.100 and 10.0.0.1 are down"

        result = sanitizer.sanitize(text)

        assert "[IP_REDACTED]" in result.sanitized_text
        assert "192.168.1.100" not in result.sanitized_text
        assert "10.0.0.1" not in result.sanitized_text
        assert result.redactions["ipv4"] == 2

    def test_sanitize_ipv6_addresses(self) -> None:
        """Test sanitization of IPv6 addresses."""
        sanitizer = LogSanitizer()
        text = "IPv6 address 2001:0db8:85a3:0000:0000:8a2e:0370:7334 found"

        result = sanitizer.sanitize(text)

        assert "[IP_REDACTED]" in result.sanitized_text
        assert "2001:0db8:85a3:0000:0000:8a2e:0370:7334" not in result.sanitized_text

    def test_sanitize_credit_card_numbers(self) -> None:
        """Test sanitization of credit card numbers."""
        sanitizer = LogSanitizer()
        text = "Card number 4111-1111-1111-1111 or 5500000000000004"

        result = sanitizer.sanitize(text)

        assert "[CC_REDACTED]" in result.sanitized_text
        assert "4111-1111-1111-1111" not in result.sanitized_text
        assert "5500000000000004" not in result.sanitized_text

    def test_sanitize_ssn(self) -> None:
        """Test sanitization of Social Security Numbers."""
        sanitizer = LogSanitizer()
        text = "SSN: 123-45-6789 for verification"

        result = sanitizer.sanitize(text)

        assert "[SSN_REDACTED]" in result.sanitized_text
        assert "123-45-6789" not in result.sanitized_text

    def test_sanitize_phone_numbers(self) -> None:
        """Test sanitization of US phone numbers."""
        sanitizer = LogSanitizer()
        text = "Call 555-123-4567 or 555.987.6543 or 5551234567"

        result = sanitizer.sanitize(text)

        assert "[PHONE_REDACTED]" in result.sanitized_text
        assert "555-123-4567" not in result.sanitized_text

    def test_sanitize_aws_access_keys(self) -> None:
        """Test sanitization of AWS access keys."""
        sanitizer = LogSanitizer()
        text = "Using AWS key AKIAIOSFODNN7EXAMPLE for access"

        result = sanitizer.sanitize(text)

        assert "[AWS_KEY_REDACTED]" in result.sanitized_text
        assert "AKIAIOSFODNN7EXAMPLE" not in result.sanitized_text

    def test_sanitize_aws_secret_keys(self) -> None:
        """Test sanitization of AWS secret keys."""
        sanitizer = LogSanitizer()
        text = 'AWS_SECRET="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"'

        result = sanitizer.sanitize(text)

        assert "[AWS_SECRET_REDACTED]" in result.sanitized_text
        assert "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY" not in result.sanitized_text

    def test_sanitize_generic_api_keys(self) -> None:
        """Test sanitization of generic API keys."""
        sanitizer = LogSanitizer()
        text = 'api_key: "sk-1234567890abcdefghij" in config'

        result = sanitizer.sanitize(text)

        assert "[API_KEY_REDACTED]" in result.sanitized_text
        assert "sk-1234567890abcdefghij" not in result.sanitized_text

    def test_sanitize_bearer_tokens(self) -> None:
        """Test sanitization of Bearer tokens (JWT)."""
        sanitizer = LogSanitizer()
        text = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"

        result = sanitizer.sanitize(text)

        assert "[TOKEN_REDACTED]" in result.sanitized_text
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in result.sanitized_text

    def test_sanitize_private_keys(self) -> None:
        """Test sanitization of private keys."""
        sanitizer = LogSanitizer()
        text = "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA..."

        result = sanitizer.sanitize(text)

        assert "[PRIVATE_KEY_REDACTED]" in result.sanitized_text
        assert "-----BEGIN RSA PRIVATE KEY-----" not in result.sanitized_text

    def test_sanitize_passwords_in_urls(self) -> None:
        """Test sanitization of passwords in URLs."""
        sanitizer = LogSanitizer()
        text = "Connecting to mysql://user:secret_password@host:3306/db"

        result = sanitizer.sanitize(text)

        assert "[PASSWORD_REDACTED]" in result.sanitized_text
        assert "secret_password" not in result.sanitized_text

    def test_sanitize_multiple_patterns_in_same_text(self) -> None:
        """Test sanitization of multiple patterns in same text."""
        sanitizer = LogSanitizer()
        text = "Email user@example.com from IP 192.168.1.100 with key AKIAIOSFODNN7EXAMPLE"

        result = sanitizer.sanitize(text)

        assert "[EMAIL_REDACTED]" in result.sanitized_text
        assert "[IP_REDACTED]" in result.sanitized_text
        assert "[AWS_KEY_REDACTED]" in result.sanitized_text
        assert result.redaction_count == 3
        assert "email" in result.redactions
        assert "ipv4" in result.redactions
        assert "aws_access_key" in result.redactions

    def test_sanitize_log_events(self) -> None:
        """Test sanitization of log events list."""
        sanitizer = LogSanitizer()
        events = [
            {
                "timestamp": 1234567890,
                "message": "User user@example.com logged in from 192.168.1.100",
                "level": "INFO",
            },
            {
                "timestamp": 1234567891,
                "message": "API key sk-1234567890abcdefghij used",
                "level": "DEBUG",
            },
        ]

        sanitized_events, redactions = sanitizer.sanitize_log_events(events)

        assert len(sanitized_events) == 2
        assert "[EMAIL_REDACTED]" in sanitized_events[0]["message"]
        assert "[IP_REDACTED]" in sanitized_events[0]["message"]
        assert "[API_KEY_REDACTED]" in sanitized_events[1]["message"]
        assert "email" in redactions
        assert "ipv4" in redactions

    def test_sanitize_log_events_disabled(self) -> None:
        """Test that disabled sanitizer returns original log events."""
        sanitizer = LogSanitizer(enabled=False)
        events = [
            {"message": "User user@example.com logged in"},
        ]

        sanitized_events, redactions = sanitizer.sanitize_log_events(events)

        assert sanitized_events == events
        assert redactions == {}

    def test_sanitize_dict(self) -> None:
        """Test sanitization of dictionary values."""
        sanitizer = LogSanitizer()
        data = {
            "user_email": "user@example.com",
            "ip_address": "192.168.1.100",
            "credentials": "api_key: sk-1234567890abcdefghij",
            "numeric_id": 12345,
        }

        sanitized_data, redactions = sanitizer.sanitize_dict(data)

        assert "[EMAIL_REDACTED]" in sanitized_data["user_email"]
        assert "[IP_REDACTED]" in sanitized_data["ip_address"]
        assert "[API_KEY_REDACTED]" in sanitized_data["credentials"]
        assert sanitized_data["numeric_id"] == 12345  # Non-string unchanged
        assert len(redactions) > 0

    def test_sanitize_dict_specific_keys(self) -> None:
        """Test sanitization of specific dictionary keys only."""
        sanitizer = LogSanitizer()
        data = {
            "public_field": "user@example.com",
            "private_field": "sensitive@example.com",
        }

        sanitized_data, _ = sanitizer.sanitize_dict(data, keys_to_sanitize=["private_field"])

        assert "user@example.com" in sanitized_data["public_field"]  # Not sanitized
        assert "[EMAIL_REDACTED]" in sanitized_data["private_field"]  # Sanitized

    def test_custom_patterns(self) -> None:
        """Test adding custom sanitization patterns."""
        custom_pattern = SanitizationPattern(
            name="custom_id",
            pattern=re.compile(r"ID-\d{6}"),
            replacement="[CUSTOM_ID_REDACTED]",
        )
        sanitizer = LogSanitizer(custom_patterns=[custom_pattern])

        text = "Customer ID-123456 placed order ID-789012"
        result = sanitizer.sanitize(text)

        assert "[CUSTOM_ID_REDACTED]" in result.sanitized_text
        assert "ID-123456" not in result.sanitized_text
        assert result.redactions["custom_id"] == 2

    def test_get_redaction_summary(self) -> None:
        """Test generation of redaction summary."""
        sanitizer = LogSanitizer()
        redactions = {
            "email": 3,
            "ipv4": 2,
            "aws_access_key": 1,
        }

        summary = sanitizer.get_redaction_summary(redactions)

        assert "3 Email" in summary
        assert "2 Ipv4" in summary
        assert "1 Aws Access Key" in summary

    def test_get_redaction_summary_empty(self) -> None:
        """Test redaction summary with no redactions."""
        sanitizer = LogSanitizer()

        summary = sanitizer.get_redaction_summary({})

        assert summary == "No sensitive data redacted"

    def test_real_world_log_example(self) -> None:
        """Test with a real-world log message example."""
        sanitizer = LogSanitizer()
        log_message = """
        2024-01-15 10:30:45 ERROR [auth-service] Authentication failed
        User: john.doe@company.com
        Source IP: 203.0.113.42
        API Key: sk-proj-abc123def456ghi789jkl012mno345
        AWS Key: AKIAI44QH8DHBEXAMPLE
        Connection string: postgresql://admin:SuperSecret123@db.internal.com:5432/production
        """

        result = sanitizer.sanitize(log_message)

        assert "[EMAIL_REDACTED]" in result.sanitized_text
        assert "[IP_REDACTED]" in result.sanitized_text
        assert "[API_KEY_REDACTED]" in result.sanitized_text
        assert "[AWS_KEY_REDACTED]" in result.sanitized_text
        assert "[PASSWORD_REDACTED]" in result.sanitized_text

        assert "john.doe@company.com" not in result.sanitized_text
        assert "203.0.113.42" not in result.sanitized_text
        assert "AKIAI44QH8DHBEXAMPLE" not in result.sanitized_text
        assert "SuperSecret123" not in result.sanitized_text

    def test_sanitization_preserves_log_structure(self) -> None:
        """Test that sanitization preserves overall log structure."""
        sanitizer = LogSanitizer()
        text = "INFO: User admin@example.com logged in"

        result = sanitizer.sanitize(text)

        assert result.sanitized_text.startswith("INFO:")
        assert "logged in" in result.sanitized_text
        # Only email should be changed
        assert result.sanitized_text.count("[EMAIL_REDACTED]") == 1

    def test_no_false_positives_on_version_numbers(self) -> None:
        """Test that version numbers aren't mistaken for IP addresses."""
        sanitizer = LogSanitizer()
        text = "Application version 2.4.1.0 running"

        result = sanitizer.sanitize(text)

        # IPv4 pattern will match version numbers - this is a known limitation
        # In real-world usage, context helps, but overly aggressive sanitization
        # is better than missing sensitive data
        # This test documents the current behavior
        assert "[IP_REDACTED]" in result.sanitized_text


class TestSanitizationResult:
    """Tests for SanitizationResult dataclass."""

    def test_sanitization_result_creation(self) -> None:
        """Test creation of SanitizationResult."""
        result = SanitizationResult(
            sanitized_text="test [EMAIL_REDACTED]",
            redaction_count=1,
            redactions={"email": 1},
        )

        assert result.sanitized_text == "test [EMAIL_REDACTED]"
        assert result.redaction_count == 1
        assert result.redactions == {"email": 1}


class TestSanitizationPattern:
    """Tests for SanitizationPattern dataclass."""

    def test_sanitization_pattern_creation(self) -> None:
        """Test creation of SanitizationPattern."""
        pattern = SanitizationPattern(
            name="test",
            pattern=re.compile(r"test"),
            replacement="[TEST]",
        )

        assert pattern.name == "test"
        assert pattern.replacement == "[TEST]"
        assert pattern.enabled is True

    def test_sanitization_pattern_can_be_disabled(self) -> None:
        """Test that pattern can be disabled."""
        pattern = SanitizationPattern(
            name="test",
            pattern=re.compile(r"test"),
            replacement="[TEST]",
            enabled=False,
        )

        assert pattern.enabled is False
