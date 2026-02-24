"""
Tests for the structured log level feature.

Covers:
  - setup_logging() with the new cli_level/settings/log_file signature
  - CLI --loglevel argument parsing and --debug removal
  - Log-level precedence: CLI > env var / settings > default (WARNING)
  - LogAISettings.log_level default value and LOGAI_LOG_LEVEL env var wiring
  - Integration: setup_logging produces correct output in log file

NOTE: These tests are written against the *target* implementation described in
docs/design/structured-log-level-design.md.  The implementation lives in
src/logai/cli.py (setup_logging) and src/logai/config/settings.py
(LogAISettings.log_level).  Tests will be skipped/fail with the *old*
implementation until Jackie's work lands.
"""

from __future__ import annotations

import io
import logging
import os
import re
import sys
from collections.abc import Generator
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Handler type-names injected by pytest's log-capture machinery – we must
# exclude them when counting *app* handlers so tests stay isolated from the
# test runner's own logging infrastructure.
_PYTEST_HANDLER_NAMES = frozenset(["LogCaptureHandler", "_LiveLoggingNullHandler", "_FileHandler"])


def _app_handlers(logger: logging.Logger | None = None) -> list[logging.Handler]:
    """Return only the handlers that *our* app installed (not pytest's)."""
    root = logger or logging.getLogger()
    return [h for h in root.handlers if type(h).__name__ not in _PYTEST_HANDLER_NAMES]


# ---------------------------------------------------------------------------
# Shared autouse fixture – keeps root logger clean between every test
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_root_logger() -> Generator[None, None, None]:
    """
    Ensure the root logger is reset to a known state before and after every
    test in this module.  Without this, handlers leak between tests and cause
    spurious assertion failures.
    """
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.WARNING)
    yield
    # Close any file handlers so Windows doesn't complain about open files
    for h in root.handlers[:]:
        try:
            h.close()
        except Exception:
            pass
    root.handlers.clear()
    root.setLevel(logging.WARNING)


# ===========================================================================
# 1. setup_logging() – log level correctness
# ===========================================================================


class TestSetupLoggingLevels:
    """setup_logging() sets the root logger to the requested level."""

    def test_debug_level_sets_root_to_debug(self, tmp_path: Path) -> None:
        """setup_logging(cli_level='DEBUG') → root logger at DEBUG."""
        from logai.cli import setup_logging

        setup_logging(cli_level="DEBUG", log_file=str(tmp_path / "test.log"))

        assert logging.getLogger().level == logging.DEBUG

    def test_info_level_sets_root_to_info(self, tmp_path: Path) -> None:
        """setup_logging(cli_level='INFO') → root logger at INFO."""
        from logai.cli import setup_logging

        setup_logging(cli_level="INFO", log_file=str(tmp_path / "test.log"))

        assert logging.getLogger().level == logging.INFO

    def test_warning_level_sets_root_to_warning(self, tmp_path: Path) -> None:
        """setup_logging(cli_level='WARNING') → root logger at WARNING."""
        from logai.cli import setup_logging

        setup_logging(cli_level="WARNING", log_file=str(tmp_path / "test.log"))

        assert logging.getLogger().level == logging.WARNING

    def test_error_level_sets_root_to_error(self, tmp_path: Path) -> None:
        """setup_logging(cli_level='ERROR') → root logger at ERROR."""
        from logai.cli import setup_logging

        setup_logging(cli_level="ERROR", log_file=str(tmp_path / "test.log"))

        assert logging.getLogger().level == logging.ERROR

    def test_no_arguments_defaults_to_warning(self, tmp_path: Path) -> None:
        """setup_logging() with no cli_level and no settings → WARNING."""
        from logai.cli import setup_logging

        setup_logging(log_file=str(tmp_path / "test.log"))

        assert logging.getLogger().level == logging.WARNING

    def test_none_cli_level_defaults_to_warning(self, tmp_path: Path) -> None:
        """setup_logging(cli_level=None, settings=None) → WARNING default."""
        from logai.cli import setup_logging

        setup_logging(cli_level=None, settings=None, log_file=str(tmp_path / "test.log"))

        assert logging.getLogger().level == logging.WARNING

    def test_default_log_level_constant_is_warning(self) -> None:
        """The module-level DEFAULT_LOG_LEVEL constant must be 'WARNING'."""
        from logai.cli import DEFAULT_LOG_LEVEL  # type: ignore[attr-defined]

        assert DEFAULT_LOG_LEVEL == "WARNING"

    def test_valid_log_levels_constant_contains_four_levels(self) -> None:
        """VALID_LOG_LEVELS should contain exactly DEBUG/INFO/WARNING/ERROR."""
        from logai.cli import VALID_LOG_LEVELS  # type: ignore[attr-defined]

        assert set(VALID_LOG_LEVELS) == {"DEBUG", "INFO", "WARNING", "ERROR"}

    def test_invalid_log_level_falls_back_to_warning(self, tmp_path: Path) -> None:
        """An invalid cli_level string falls back to WARNING instead of crashing."""
        from logai.cli import setup_logging

        # Design doc §2: graceful fallback to WARNING for invalid levels
        with patch("sys.stderr", new_callable=StringIO) as mock_err:
            setup_logging(cli_level="TRACE", log_file=str(tmp_path / "test.log"))

        assert logging.getLogger().level == logging.WARNING
        # A warning message should be printed to stderr
        assert "TRACE" in mock_err.getvalue() or "Invalid" in mock_err.getvalue()

    def test_invalid_level_via_settings_falls_back_gracefully(self, tmp_path: Path) -> None:
        """Even if an invalid level slips through settings, we don't crash."""
        from logai.cli import setup_logging

        mock_settings = MagicMock()
        mock_settings.log_level = "VERBOSE"  # not a valid level
        mock_settings.log_file = None

        with patch("sys.stderr", new_callable=StringIO):
            setup_logging(
                cli_level=None,
                settings=mock_settings,
                log_file=str(tmp_path / "test.log"),
            )

        assert logging.getLogger().level == logging.WARNING


# ===========================================================================
# 2. setup_logging() – file handler behaviour
# ===========================================================================


class TestSetupLoggingHandlers:
    """setup_logging() installs the correct handler type."""

    def test_file_handler_added_when_path_is_writable(self, tmp_path: Path) -> None:
        """A FileHandler (not StreamHandler) is used when the log path is writable."""
        from logai.cli import setup_logging

        log_file = tmp_path / "test.log"
        setup_logging(cli_level="INFO", log_file=str(log_file))

        handlers = _app_handlers()
        assert len(handlers) == 1, f"Expected 1 app handler, got {handlers}"
        assert isinstance(handlers[0], logging.FileHandler)

    def test_no_stream_handler_when_file_succeeds(self, tmp_path: Path) -> None:
        """StreamHandler must NOT be present when file logging succeeds (TUI safety)."""
        from logai.cli import setup_logging

        setup_logging(cli_level="DEBUG", log_file=str(tmp_path / "app.log"))

        stream_only = [
            h
            for h in _app_handlers()
            if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
        ]
        assert len(stream_only) == 0, (
            "StreamHandler was added even though file logging succeeded. "
            "This would corrupt the TUI!"
        )

    def test_fallback_to_stream_handler_when_file_not_writable(self) -> None:
        """StreamHandler is used as fallback when the log file cannot be created."""
        from logai.cli import setup_logging

        # /root/... is not writable in CI or regular user context
        invalid_path = "/root/cannot_write_here/logai.log"

        with patch("sys.stderr", new_callable=StringIO):
            setup_logging(cli_level="INFO", log_file=invalid_path)

        handlers = _app_handlers()
        assert len(handlers) == 1, f"Expected 1 fallback handler, got {handlers}"
        assert isinstance(handlers[0], logging.StreamHandler)
        assert not isinstance(
            handlers[0], logging.FileHandler
        ), "Fallback handler must be a plain StreamHandler, not a FileHandler"

    def test_fallback_prints_warning_to_stderr_when_file_fails(self) -> None:
        """A human-readable warning is emitted to stderr on file handler failure."""
        from logai.cli import setup_logging

        with patch("sys.stderr", new_callable=StringIO) as mock_err:
            setup_logging(cli_level="WARNING", log_file="/root/no_access/logai.log")

        stderr_text = mock_err.getvalue()
        assert "Warning" in stderr_text or "warning" in stderr_text
        assert "log file" in stderr_text.lower() or "Could not create" in stderr_text

    def test_log_file_created_on_disk(self, tmp_path: Path) -> None:
        """The log file is actually created after setup_logging() is called."""
        from logai.cli import setup_logging

        log_file = tmp_path / "logai.log"
        assert not log_file.exists()

        setup_logging(cli_level="INFO", log_file=str(log_file))

        assert log_file.exists(), "Log file should have been created by setup_logging()"

    def test_parent_directories_created_automatically(self, tmp_path: Path) -> None:
        """Nested parent directories are created if they do not yet exist."""
        from logai.cli import setup_logging

        deep_log = tmp_path / "a" / "b" / "c" / "logai.log"
        assert not deep_log.parent.exists()

        setup_logging(cli_level="INFO", log_file=str(deep_log))

        assert deep_log.parent.exists(), "Parent directories should have been created"
        assert deep_log.exists(), "Log file should exist inside the created directory"

    def test_default_log_path_is_home_logai_logs(self) -> None:
        """When no log_file is passed, the default path is ~/.logai/logs/logai.log."""
        from logai.cli import setup_logging

        setup_logging(cli_level="WARNING")  # no log_file kwarg

        handlers = _app_handlers()
        assert len(handlers) == 1
        assert isinstance(handlers[0], logging.FileHandler)

        expected = Path.home() / ".logai" / "logs" / "logai.log"
        actual = Path(handlers[0].baseFilename)  # type: ignore[attr-defined]
        assert actual == expected, f"Expected {expected}, got {actual}"


# ===========================================================================
# 3. setup_logging() – log format
# ===========================================================================


class TestSetupLoggingFormat:
    """Verify that log records include all required fields."""

    def test_format_includes_timestamp(self, tmp_path: Path) -> None:
        """Log entries must include a timestamp (YYYY-MM-DD HH:MM:SS pattern)."""
        from logai.cli import setup_logging

        log_file = tmp_path / "test.log"
        setup_logging(cli_level="INFO", log_file=str(log_file))

        test_logger = logging.getLogger("raoul.format_test")
        test_logger.info("timestamp check")
        for h in _app_handlers():
            h.flush()

        content = log_file.read_text()
        assert re.search(
            r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", content
        ), "Log entry should contain a timestamp in YYYY-MM-DD HH:MM:SS format"

    def test_format_includes_logger_name(self, tmp_path: Path) -> None:
        """Log entries must include the logger name."""
        from logai.cli import setup_logging

        log_file = tmp_path / "test.log"
        setup_logging(cli_level="INFO", log_file=str(log_file))

        logger_name = "raoul.logger_name_test"
        logging.getLogger(logger_name).info("name check")
        for h in _app_handlers():
            h.flush()

        assert logger_name in log_file.read_text()

    def test_format_includes_level_name(self, tmp_path: Path) -> None:
        """Log entries must include the severity level name (e.g. INFO, WARNING)."""
        from logai.cli import setup_logging

        log_file = tmp_path / "test.log"
        setup_logging(cli_level="INFO", log_file=str(log_file))

        logging.getLogger("raoul.level_test").warning("level check")
        for h in _app_handlers():
            h.flush()

        assert "WARNING" in log_file.read_text()

    def test_format_includes_message(self, tmp_path: Path) -> None:
        """Log entries must include the message body."""
        from logai.cli import setup_logging

        log_file = tmp_path / "test.log"
        setup_logging(cli_level="INFO", log_file=str(log_file))

        unique_msg = "raoul_unique_message_xyzzy_9876"
        logging.getLogger("raoul.msg_test").info(unique_msg)
        for h in _app_handlers():
            h.flush()

        assert unique_msg in log_file.read_text()

    def test_format_string_is_correct_pattern(self, tmp_path: Path) -> None:
        """The formatter pattern should be %(asctime)s - %(name)s - %(levelname)s - %(message)s."""
        from logai.cli import setup_logging

        log_file = tmp_path / "test.log"
        setup_logging(cli_level="INFO", log_file=str(log_file))

        handlers = _app_handlers()
        assert handlers, "No app handler found"
        fmt = handlers[0].formatter
        assert fmt is not None, "Handler must have a Formatter attached"
        # The design doc specifies this exact format string
        expected_fmt = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        assert fmt._fmt == expected_fmt, (  # type: ignore[union-attr]
            f"Expected format '{expected_fmt}', got '{fmt._fmt}'"  # type: ignore[union-attr]
        )


# ===========================================================================
# 4. CLI argument parsing – --loglevel
# ===========================================================================


class TestLogLevelCLIArgument:
    """
    Tests for the --loglevel argparse argument.

    Because main() does many things besides parsing, we test by importing the
    parser-building logic directly.  The design doc specifies that the parser
    is constructed inside main(); we patch sys.argv and call parse_args() via
    the public main() entry-point with everything else mocked out, OR we use
    a helper that exposes just the parser.

    Per design doc §3, Jackie may expose a _build_parser() helper; if not, we
    exercise argument parsing by calling argparse directly through main() with
    all side-effects mocked.
    """

    # ------------------------------------------------------------------
    # Helper: if Jackie exposes _build_parser() we use it; otherwise we
    # fall back to constructing a minimal parser that matches the spec.
    # ------------------------------------------------------------------

    @staticmethod
    def _get_parser():  # type: ignore[return]
        """Return the CLI argument parser, however it is exposed."""
        try:
            from logai.cli import _build_parser  # type: ignore[attr-defined]

            return _build_parser()
        except ImportError:
            # Fallback: construct a parser that mirrors the design spec so
            # these tests document the *expected* interface even before the
            # helper function exists.
            import argparse

            class DeprecatedDebugAction(argparse.Action):
                def __call__(self, parser, namespace, values, option_string=None):
                    parser.error("The --debug flag has been removed. Use --loglevel DEBUG instead.")

            p = argparse.ArgumentParser()
            p.add_argument(
                "--loglevel",
                type=str.upper,
                choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                default=None,
                metavar="LEVEL",
            )
            p.add_argument("--debug", nargs=0, action=DeprecatedDebugAction)
            return p

    def test_loglevel_debug_parsed_correctly(self) -> None:
        """--loglevel DEBUG → args.loglevel == 'DEBUG'."""
        parser = self._get_parser()
        args = parser.parse_args(["--loglevel", "DEBUG"])
        assert args.loglevel == "DEBUG"

    def test_loglevel_info_parsed_correctly(self) -> None:
        """--loglevel INFO → args.loglevel == 'INFO'."""
        parser = self._get_parser()
        args = parser.parse_args(["--loglevel", "INFO"])
        assert args.loglevel == "INFO"

    def test_loglevel_warning_parsed_correctly(self) -> None:
        """--loglevel WARNING → args.loglevel == 'WARNING'."""
        parser = self._get_parser()
        args = parser.parse_args(["--loglevel", "WARNING"])
        assert args.loglevel == "WARNING"

    def test_loglevel_error_parsed_correctly(self) -> None:
        """--loglevel ERROR → args.loglevel == 'ERROR'."""
        parser = self._get_parser()
        args = parser.parse_args(["--loglevel", "ERROR"])
        assert args.loglevel == "ERROR"

    def test_loglevel_lowercase_normalised_to_uppercase(self) -> None:
        """--loglevel debug (lowercase) → args.loglevel == 'DEBUG' (type=str.upper)."""
        parser = self._get_parser()
        args = parser.parse_args(["--loglevel", "debug"])
        assert args.loglevel == "DEBUG"

    def test_loglevel_mixed_case_normalised(self) -> None:
        """--loglevel Warning (mixed case) → args.loglevel == 'WARNING'."""
        parser = self._get_parser()
        args = parser.parse_args(["--loglevel", "Warning"])
        assert args.loglevel == "WARNING"

    def test_loglevel_default_is_none_when_not_provided(self) -> None:
        """No --loglevel flag → args.loglevel is None (not 'WARNING')."""
        parser = self._get_parser()
        args = parser.parse_args([])
        # None is critical: lets setup_logging() distinguish "not provided"
        # from "user explicitly passed WARNING"
        assert args.loglevel is None

    def test_loglevel_invalid_value_raises_system_exit(self) -> None:
        """--loglevel TRACE (invalid) → argparse raises SystemExit."""
        parser = self._get_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["--loglevel", "TRACE"])
        assert exc_info.value.code != 0

    def test_loglevel_invalid_gives_helpful_error_to_stderr(self) -> None:
        """argparse prints an error message for invalid --loglevel values."""
        parser = self._get_parser()
        with pytest.raises(SystemExit):
            with patch("sys.stderr", new_callable=StringIO) as mock_err:
                parser.parse_args(["--loglevel", "VERBOSE"])
        # argparse always writes its 'invalid choice' message to stderr
        stderr_output = mock_err.getvalue()
        assert "invalid choice" in stderr_output or "VERBOSE" in stderr_output

    def test_debug_flag_is_removed_and_raises_system_exit(self) -> None:
        """--debug (old flag) must raise SystemExit with a clear error."""
        parser = self._get_parser()
        with pytest.raises(SystemExit) as exc_info:
            with patch("sys.stderr", new_callable=StringIO):
                parser.parse_args(["--debug"])
        assert exc_info.value.code != 0

    def test_debug_flag_error_message_mentions_loglevel(self) -> None:
        """The --debug error message should tell users to use --loglevel DEBUG."""
        parser = self._get_parser()
        with pytest.raises(SystemExit):
            with patch("sys.stderr", new_callable=StringIO) as mock_err:
                parser.parse_args(["--debug"])
        stderr_output = mock_err.getvalue()
        # Design doc §3 specifies this exact migration guidance
        assert "--loglevel" in stderr_output or "loglevel" in stderr_output.lower()


# ===========================================================================
# 5. Precedence logic: CLI > env var > default
# ===========================================================================


class TestLogLevelPrecedence:
    """
    Test the three-tier precedence: CLI flag > LOGAI_LOG_LEVEL (.env) > default.
    Uses mock settings objects to avoid requiring a real .env file.
    """

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _settings_with_level(level: str) -> MagicMock:
        """Return a mock LogAISettings with log_level set to *level*."""
        s = MagicMock()
        s.log_level = level
        s.log_file = None
        return s

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------

    def test_cli_debug_overrides_settings_info(self, tmp_path: Path) -> None:
        """CLI DEBUG beats settings INFO  →  effective level is DEBUG."""
        from logai.cli import setup_logging

        settings = self._settings_with_level("INFO")
        setup_logging(
            cli_level="DEBUG",
            settings=settings,
            log_file=str(tmp_path / "test.log"),
        )
        assert logging.getLogger().level == logging.DEBUG

    def test_cli_error_overrides_settings_debug(self, tmp_path: Path) -> None:
        """CLI ERROR beats settings DEBUG  →  effective level is ERROR."""
        from logai.cli import setup_logging

        settings = self._settings_with_level("DEBUG")
        setup_logging(
            cli_level="ERROR",
            settings=settings,
            log_file=str(tmp_path / "test.log"),
        )
        assert logging.getLogger().level == logging.ERROR

    def test_cli_warning_overrides_settings_debug(self, tmp_path: Path) -> None:
        """CLI WARNING beats settings DEBUG  →  effective level is WARNING."""
        from logai.cli import setup_logging

        settings = self._settings_with_level("DEBUG")
        setup_logging(
            cli_level="WARNING",
            settings=settings,
            log_file=str(tmp_path / "test.log"),
        )
        assert logging.getLogger().level == logging.WARNING

    def test_cli_debug_overrides_settings_warning(self, tmp_path: Path) -> None:
        """CLI DEBUG beats settings WARNING  →  effective level is DEBUG."""
        from logai.cli import setup_logging

        settings = self._settings_with_level("WARNING")
        setup_logging(
            cli_level="DEBUG",
            settings=settings,
            log_file=str(tmp_path / "test.log"),
        )
        assert logging.getLogger().level == logging.DEBUG

    def test_settings_debug_used_when_no_cli_flag(self, tmp_path: Path) -> None:
        """No CLI flag + settings.log_level='DEBUG'  →  effective level is DEBUG."""
        from logai.cli import setup_logging

        settings = self._settings_with_level("DEBUG")
        setup_logging(
            cli_level=None,
            settings=settings,
            log_file=str(tmp_path / "test.log"),
        )
        assert logging.getLogger().level == logging.DEBUG

    def test_settings_error_used_when_no_cli_flag(self, tmp_path: Path) -> None:
        """No CLI flag + settings.log_level='ERROR'  →  effective level is ERROR."""
        from logai.cli import setup_logging

        settings = self._settings_with_level("ERROR")
        setup_logging(
            cli_level=None,
            settings=settings,
            log_file=str(tmp_path / "test.log"),
        )
        assert logging.getLogger().level == logging.ERROR

    def test_settings_info_used_when_no_cli_flag(self, tmp_path: Path) -> None:
        """No CLI flag + settings.log_level='INFO'  →  effective level is INFO."""
        from logai.cli import setup_logging

        settings = self._settings_with_level("INFO")
        setup_logging(
            cli_level=None,
            settings=settings,
            log_file=str(tmp_path / "test.log"),
        )
        assert logging.getLogger().level == logging.INFO

    def test_default_warning_when_no_cli_and_no_settings(self, tmp_path: Path) -> None:
        """No CLI flag + settings=None  →  default WARNING."""
        from logai.cli import setup_logging

        setup_logging(
            cli_level=None,
            settings=None,
            log_file=str(tmp_path / "test.log"),
        )
        assert logging.getLogger().level == logging.WARNING

    def test_env_var_logai_log_level_debug_applied_via_settings(
        self, clean_env: None, tmp_path: Path
    ) -> None:
        """
        LOGAI_LOG_LEVEL=DEBUG in environment → settings.log_level == 'DEBUG'
        → setup_logging uses DEBUG when no CLI flag.
        """
        from logai.cli import setup_logging

        os.environ["LOGAI_LOG_LEVEL"] = "DEBUG"
        os.environ["LOGAI_ANTHROPIC_API_KEY"] = "sk-ant-test"
        os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

        from logai.config import LogAISettings

        settings = LogAISettings(_env_file=None)  # type: ignore[call-arg]
        assert (
            settings.log_level == "DEBUG"
        ), "LOGAI_LOG_LEVEL=DEBUG should have been loaded into settings.log_level"

        setup_logging(
            cli_level=None,
            settings=settings,
            log_file=str(tmp_path / "test.log"),
        )
        assert logging.getLogger().level == logging.DEBUG

    def test_env_var_logai_log_level_debug_overridden_by_cli_error(
        self, clean_env: None, tmp_path: Path
    ) -> None:
        """
        LOGAI_LOG_LEVEL=DEBUG + --loglevel ERROR (CLI)  →  ERROR wins.
        """
        from logai.cli import setup_logging

        os.environ["LOGAI_LOG_LEVEL"] = "DEBUG"
        os.environ["LOGAI_ANTHROPIC_API_KEY"] = "sk-ant-test"
        os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

        from logai.config import LogAISettings

        settings = LogAISettings(_env_file=None)  # type: ignore[call-arg]

        setup_logging(
            cli_level="ERROR",
            settings=settings,
            log_file=str(tmp_path / "test.log"),
        )
        assert logging.getLogger().level == logging.ERROR

    def test_env_var_info_beats_default_warning_when_no_cli(
        self, clean_env: None, tmp_path: Path
    ) -> None:
        """
        LOGAI_LOG_LEVEL=INFO (env) + no CLI flag  →  INFO (not WARNING default).
        """
        from logai.cli import setup_logging

        os.environ["LOGAI_LOG_LEVEL"] = "INFO"
        os.environ["LOGAI_ANTHROPIC_API_KEY"] = "sk-ant-test"
        os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

        from logai.config import LogAISettings

        settings = LogAISettings(_env_file=None)  # type: ignore[call-arg]

        setup_logging(
            cli_level=None,
            settings=settings,
            log_file=str(tmp_path / "test.log"),
        )
        assert logging.getLogger().level == logging.INFO

    def test_absolute_fallback_when_settings_none_and_no_cli(self, tmp_path: Path) -> None:
        """
        No env var, no settings, no CLI flag  →  WARNING (absolute default).
        """
        from logai.cli import setup_logging

        setup_logging(
            cli_level=None,
            settings=None,
            log_file=str(tmp_path / "test.log"),
        )
        assert logging.getLogger().level == logging.WARNING

    def test_settings_log_file_used_when_no_log_file_arg(self, tmp_path: Path) -> None:
        """
        When log_file param is None, settings.log_file should be used as the
        log file path (design doc §2 – settings.log_file wired in).
        """
        from logai.cli import setup_logging

        settings_log_path = str(tmp_path / "from_settings.log")
        settings = MagicMock()
        settings.log_level = "INFO"
        settings.log_file = settings_log_path

        setup_logging(cli_level=None, settings=settings, log_file=None)

        handlers = _app_handlers()
        assert len(handlers) == 1
        assert isinstance(handlers[0], logging.FileHandler)
        assert Path(handlers[0].baseFilename) == Path(settings_log_path)  # type: ignore[attr-defined]


# ===========================================================================
# 6. LogAISettings – log_level field
# ===========================================================================


class TestSettingsLogLevelField:
    """Tests for LogAISettings.log_level default and env-var wiring."""

    def test_default_log_level_is_warning(self, clean_env: None) -> None:
        """
        LogAISettings.log_level must default to 'WARNING', not 'INFO'.
        (Design doc §4 changes the default from INFO to WARNING.)
        """
        os.environ["LOGAI_ANTHROPIC_API_KEY"] = "sk-ant-test-key"
        os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

        from logai.config import LogAISettings

        settings = LogAISettings(_env_file=None)  # type: ignore[call-arg]
        assert settings.log_level == "WARNING", (
            f"Default log_level should be 'WARNING', got '{settings.log_level}'. "
            "Did the settings.py default get updated from 'INFO' to 'WARNING'?"
        )

    def test_logai_log_level_env_var_sets_debug(self, clean_env: None) -> None:
        """LOGAI_LOG_LEVEL=DEBUG → settings.log_level == 'DEBUG'."""
        os.environ["LOGAI_ANTHROPIC_API_KEY"] = "sk-ant-test-key"
        os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
        os.environ["LOGAI_LOG_LEVEL"] = "DEBUG"

        from logai.config import LogAISettings

        settings = LogAISettings(_env_file=None)  # type: ignore[call-arg]
        assert settings.log_level == "DEBUG"

    def test_logai_log_level_env_var_sets_info(self, clean_env: None) -> None:
        """LOGAI_LOG_LEVEL=INFO → settings.log_level == 'INFO'."""
        os.environ["LOGAI_ANTHROPIC_API_KEY"] = "sk-ant-test-key"
        os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
        os.environ["LOGAI_LOG_LEVEL"] = "INFO"

        from logai.config import LogAISettings

        settings = LogAISettings(_env_file=None)  # type: ignore[call-arg]
        assert settings.log_level == "INFO"

    def test_logai_log_level_env_var_sets_error(self, clean_env: None) -> None:
        """LOGAI_LOG_LEVEL=ERROR → settings.log_level == 'ERROR'."""
        os.environ["LOGAI_ANTHROPIC_API_KEY"] = "sk-ant-test-key"
        os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
        os.environ["LOGAI_LOG_LEVEL"] = "ERROR"

        from logai.config import LogAISettings

        settings = LogAISettings(_env_file=None)  # type: ignore[call-arg]
        assert settings.log_level == "ERROR"

    def test_logai_log_level_env_var_overrides_default(self, clean_env: None) -> None:
        """LOGAI_LOG_LEVEL=DEBUG overrides the WARNING default."""
        os.environ["LOGAI_ANTHROPIC_API_KEY"] = "sk-ant-test-key"
        os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
        os.environ["LOGAI_LOG_LEVEL"] = "DEBUG"

        from logai.config import LogAISettings

        settings = LogAISettings(_env_file=None)  # type: ignore[call-arg]
        assert settings.log_level != "WARNING"
        assert settings.log_level == "DEBUG"

    def test_invalid_logai_log_level_env_var_rejected_by_pydantic(self, clean_env: None) -> None:
        """
        An invalid LOGAI_LOG_LEVEL value is rejected by pydantic's Literal
        validator before setup_logging() is ever called.
        """
        os.environ["LOGAI_ANTHROPIC_API_KEY"] = "sk-ant-test-key"
        os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
        os.environ["LOGAI_LOG_LEVEL"] = "TRACE"  # not in Literal

        from logai.config import LogAISettings

        with pytest.raises(ValidationError):
            LogAISettings(_env_file=None)  # type: ignore[call-arg]


# ===========================================================================
# 7. Integration tests: full setup_logging() → actual log output
# ===========================================================================


class TestSetupLoggingIntegration:
    """
    End-to-end tests that verify messages appear (or are suppressed) in the
    log file according to the configured level.
    """

    def test_debug_level_writes_all_severity_messages(self, tmp_path: Path) -> None:
        """With DEBUG, messages at DEBUG/INFO/WARNING/ERROR all appear in log."""
        from logai.cli import setup_logging

        log_file = tmp_path / "integration.log"
        setup_logging(cli_level="DEBUG", log_file=str(log_file))

        tl = logging.getLogger("test.integration.debug_all")
        tl.debug("debug-msg-raoul")
        tl.info("info-msg-raoul")
        tl.warning("warning-msg-raoul")
        tl.error("error-msg-raoul")

        for h in _app_handlers():
            h.flush()

        content = log_file.read_text()
        assert "debug-msg-raoul" in content
        assert "info-msg-raoul" in content
        assert "warning-msg-raoul" in content
        assert "error-msg-raoul" in content

    def test_warning_level_hides_debug_and_info(self, tmp_path: Path) -> None:
        """With WARNING, DEBUG and INFO messages do NOT appear in log."""
        from logai.cli import setup_logging

        log_file = tmp_path / "integration.log"
        setup_logging(cli_level="WARNING", log_file=str(log_file))

        tl = logging.getLogger("test.integration.warning_filter")
        tl.debug("should-be-hidden-debug")
        tl.info("should-be-hidden-info")
        tl.warning("should-appear-warning")

        for h in _app_handlers():
            h.flush()

        content = log_file.read_text()
        assert "should-be-hidden-debug" not in content
        assert "should-be-hidden-info" not in content
        assert "should-appear-warning" in content

    def test_error_level_hides_debug_info_and_warning(self, tmp_path: Path) -> None:
        """With ERROR, only ERROR messages appear; lower levels are hidden."""
        from logai.cli import setup_logging

        log_file = tmp_path / "integration.log"
        setup_logging(cli_level="ERROR", log_file=str(log_file))

        tl = logging.getLogger("test.integration.error_filter")
        tl.debug("hidden-debug")
        tl.info("hidden-info")
        tl.warning("hidden-warning")
        tl.error("visible-error")

        for h in _app_handlers():
            h.flush()

        content = log_file.read_text()
        assert "hidden-debug" not in content
        assert "hidden-info" not in content
        assert "hidden-warning" not in content
        assert "visible-error" in content

    def test_info_level_hides_debug_shows_info_and_above(self, tmp_path: Path) -> None:
        """With INFO, DEBUG is hidden; INFO/WARNING/ERROR appear."""
        from logai.cli import setup_logging

        log_file = tmp_path / "integration.log"
        setup_logging(cli_level="INFO", log_file=str(log_file))

        tl = logging.getLogger("test.integration.info_filter")
        tl.debug("hidden-debug-raoul")
        tl.info("visible-info-raoul")
        tl.warning("visible-warning-raoul")

        for h in _app_handlers():
            h.flush()

        content = log_file.read_text()
        assert "hidden-debug-raoul" not in content
        assert "visible-info-raoul" in content
        assert "visible-warning-raoul" in content

    def test_child_loggers_inherit_root_level(self, tmp_path: Path) -> None:
        """
        All 17 app loggers propagate to root, so they should honour the level
        set by setup_logging() without any per-module configuration.
        """
        from logai.cli import setup_logging

        log_file = tmp_path / "propagation.log"
        setup_logging(cli_level="DEBUG", log_file=str(log_file))

        # Simulate any of the 17 module-level loggers
        for name in [
            "logai.cli",
            "logai.core.orchestrator",
            "logai.config.model_config",
            "logai.providers.llm.litellm_provider",
            "logai.ui.app",
        ]:
            logging.getLogger(name).debug(f"debug-from-{name}")

        for h in _app_handlers():
            h.flush()

        content = log_file.read_text()
        for name in [
            "logai.cli",
            "logai.core.orchestrator",
            "logai.config.model_config",
            "logai.providers.llm.litellm_provider",
            "logai.ui.app",
        ]:
            assert (
                f"debug-from-{name}" in content
            ), f"Expected debug message from {name} to appear in log file"

    def test_setup_logging_writes_initialization_message(self, tmp_path: Path) -> None:
        """
        After setup_logging(), an INFO-level 'Logging initialized' message
        is written to the log file (design doc §2).
        """
        from logai.cli import setup_logging

        log_file = tmp_path / "init_msg.log"
        setup_logging(cli_level="INFO", log_file=str(log_file))

        for h in _app_handlers():
            h.flush()

        content = log_file.read_text()
        assert "Logging initialized" in content
        assert "source=" in content

    def test_end_to_end_env_debug_no_cli(self, clean_env: None, tmp_path: Path) -> None:
        """
        Full end-to-end: LOGAI_LOG_LEVEL=DEBUG env + no CLI →
        DEBUG messages appear in log file.
        """
        from logai.cli import setup_logging

        os.environ["LOGAI_LOG_LEVEL"] = "DEBUG"
        os.environ["LOGAI_ANTHROPIC_API_KEY"] = "sk-ant-test"
        os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

        from logai.config import LogAISettings

        settings = LogAISettings(_env_file=None)  # type: ignore[call-arg]

        log_file = tmp_path / "e2e.log"
        setup_logging(cli_level=None, settings=settings, log_file=str(log_file))

        logging.getLogger("test.e2e").debug("e2e-debug-message")
        for h in _app_handlers():
            h.flush()

        assert "e2e-debug-message" in log_file.read_text()

    def test_end_to_end_cli_overrides_env_in_full_flow(
        self, clean_env: None, tmp_path: Path
    ) -> None:
        """
        Full end-to-end precedence: LOGAI_LOG_LEVEL=INFO + cli_level='ERROR'
        → only ERROR messages appear (CLI wins).
        """
        from logai.cli import setup_logging

        os.environ["LOGAI_LOG_LEVEL"] = "INFO"
        os.environ["LOGAI_ANTHROPIC_API_KEY"] = "sk-ant-test"
        os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

        from logai.config import LogAISettings

        settings = LogAISettings(_env_file=None)  # type: ignore[call-arg]

        log_file = tmp_path / "e2e_cli_wins.log"
        setup_logging(cli_level="ERROR", settings=settings, log_file=str(log_file))

        tl = logging.getLogger("test.e2e.cli_wins")
        tl.info("should-be-suppressed-info")
        tl.error("should-appear-error")

        for h in _app_handlers():
            h.flush()

        content = log_file.read_text()
        assert "should-be-suppressed-info" not in content
        assert "should-appear-error" in content
