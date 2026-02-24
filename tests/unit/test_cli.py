"""Tests for CLI argument parsing and settings override."""

import io
import logging
import os
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from logai.cli import main


class TestCLIArgumentParsing:
    """Test suite for CLI argument parsing."""

    def test_help_message_displays(self) -> None:
        """Test that --help displays help message with new arguments."""
        with patch("sys.argv", ["logai", "--help"]):
            with pytest.raises(SystemExit) as exc_info:
                with patch("sys.stdout", new_callable=StringIO):
                    main()

            # SystemExit with code 0 is expected for --help
            assert exc_info.value.code == 0

    def test_version_displays(self) -> None:
        """Test that --version displays version information."""
        with patch("sys.argv", ["logai", "--version"]):
            with pytest.raises(SystemExit) as exc_info:
                with patch("sys.stdout", new_callable=StringIO):
                    main()

            # SystemExit with code 0 is expected for --version
            assert exc_info.value.code == 0


class TestAWSProfileCLIArgument:
    """Test suite for --aws-profile CLI argument."""

    @pytest.fixture
    def mock_components(self) -> None:
        """Mock all components to avoid actual initialization."""
        with (
            patch("logai.cli.CloudWatchDataSource"),
            patch("logai.cli.LogSanitizer"),
            patch("logai.cli.CacheManager"),
            patch("logai.cli.ToolRegistry"),
            patch("logai.cli.LiteLLMProvider"),
            patch("logai.cli.LLMOrchestrator"),
            patch("logai.cli.LogAIApp"),
        ):
            yield

    def test_aws_profile_argument_overrides_env_var(
        self, clean_env: None, mock_components: None
    ) -> None:
        """Test that --aws-profile CLI argument overrides AWS_PROFILE environment variable."""
        # Set up environment
        os.environ["LOGAI_ANTHROPIC_API_KEY"] = "sk-ant-test-key"
        os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
        os.environ["AWS_PROFILE"] = "env-profile"
        os.environ["AWS_ACCESS_KEY_ID"] = "AKIATEST"
        os.environ["AWS_SECRET_ACCESS_KEY"] = "secrettest"

        with patch("sys.argv", ["logai", "--aws-profile", "cli-profile"]):
            with patch("logai.cli.get_settings") as mock_get_settings:
                # Create a real settings object
                from logai.config import LogAISettings

                settings = LogAISettings()  # type: ignore
                mock_get_settings.return_value = settings

                with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                    # Run until app.run() is called
                    with patch("logai.cli.LogAIApp") as mock_app:
                        mock_app.return_value.run.return_value = None
                        result = main()

                # Check that CLI argument overrode environment variable
                assert settings.aws_profile == "cli-profile"
                assert result == 0

                # Check that startup output mentions CLI argument
                output = mock_stdout.getvalue()
                assert "CLI argument" in output
                assert "cli-profile" in output

    def test_aws_profile_env_var_used_when_no_cli_arg(
        self, clean_env: None, mock_components: None
    ) -> None:
        """Test that AWS_PROFILE environment variable is used when no CLI argument provided."""
        # Set up environment
        os.environ["LOGAI_ANTHROPIC_API_KEY"] = "sk-ant-test-key"
        os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
        os.environ["AWS_PROFILE"] = "env-profile"
        os.environ["AWS_ACCESS_KEY_ID"] = "AKIATEST"
        os.environ["AWS_SECRET_ACCESS_KEY"] = "secrettest"

        with patch("sys.argv", ["logai"]):
            with patch("logai.cli.get_settings") as mock_get_settings:
                from logai.config import LogAISettings

                settings = LogAISettings()  # type: ignore
                mock_get_settings.return_value = settings

                with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                    with patch("logai.cli.LogAIApp") as mock_app:
                        mock_app.return_value.run.return_value = None
                        result = main()

                # Check that environment variable was used
                assert settings.aws_profile == "env-profile"
                assert result == 0

                # Check that startup output mentions environment
                output = mock_stdout.getvalue()
                assert "environment" in output
                assert "env-profile" in output

    def test_no_profile_when_neither_provided(self, clean_env: None, mock_components: None) -> None:
        """Test that aws_profile is None when neither CLI arg nor env var provided."""
        # Set up minimal environment - explicitly unset AWS_PROFILE
        os.environ["LOGAI_ANTHROPIC_API_KEY"] = "sk-ant-test-key"
        os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
        os.environ["AWS_ACCESS_KEY_ID"] = "AKIATEST"
        os.environ["AWS_SECRET_ACCESS_KEY"] = "secrettest"
        # Ensure AWS_PROFILE is not set
        os.environ.pop("AWS_PROFILE", None)

        with patch("sys.argv", ["logai"]):
            # Mock settings to prevent .env file from being read
            with patch("logai.cli.get_settings") as mock_get_settings:
                from logai.config import LogAISettings

                # Create settings without reading .env file
                with patch.dict(os.environ, {}, clear=False):
                    # Temporarily remove AWS_PROFILE if present
                    env_copy = os.environ.copy()
                    env_copy.pop("AWS_PROFILE", None)

                    with patch.dict(os.environ, env_copy, clear=True):
                        settings = LogAISettings(_env_file=None)  # type: ignore
                        mock_get_settings.return_value = settings

                        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                            with patch("logai.cli.LogAIApp") as mock_app:
                                mock_app.return_value.run.return_value = None
                                # Suppress warning about missing credentials
                                with patch("warnings.warn"):
                                    result = main()

                        # Check that no profile is set
                        assert settings.aws_profile is None
                        assert result == 0

                        # Check that profile is not mentioned in output
                        output = mock_stdout.getvalue()
                        # Should not have profile line if profile is None
                        assert "AWS Profile:" not in output


class TestAWSRegionCLIArgument:
    """Test suite for --aws-region CLI argument."""

    @pytest.fixture
    def mock_components(self) -> None:
        """Mock all components to avoid actual initialization."""
        with (
            patch("logai.cli.CloudWatchDataSource"),
            patch("logai.cli.LogSanitizer"),
            patch("logai.cli.CacheManager"),
            patch("logai.cli.ToolRegistry"),
            patch("logai.cli.LiteLLMProvider"),
            patch("logai.cli.LLMOrchestrator"),
            patch("logai.cli.LogAIApp"),
        ):
            yield

    def test_aws_region_argument_overrides_env_var(
        self, clean_env: None, mock_components: None
    ) -> None:
        """Test that --aws-region CLI argument overrides AWS_DEFAULT_REGION."""
        # Set up environment
        os.environ["LOGAI_ANTHROPIC_API_KEY"] = "sk-ant-test-key"
        os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
        os.environ["AWS_ACCESS_KEY_ID"] = "AKIATEST"
        os.environ["AWS_SECRET_ACCESS_KEY"] = "secrettest"

        with patch("sys.argv", ["logai", "--aws-region", "eu-west-1"]):
            with patch("logai.cli.get_settings") as mock_get_settings:
                from logai.config import LogAISettings

                settings = LogAISettings()  # type: ignore
                mock_get_settings.return_value = settings

                with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                    with patch("logai.cli.LogAIApp") as mock_app:
                        mock_app.return_value.run.return_value = None
                        result = main()

                # Check that CLI argument overrode environment variable
                assert settings.aws_region == "eu-west-1"
                assert result == 0

                # Check that startup output mentions CLI argument
                output = mock_stdout.getvalue()
                assert "CLI argument" in output
                assert "eu-west-1" in output

    def test_aws_region_env_var_used_when_no_cli_arg(
        self, clean_env: None, mock_components: None
    ) -> None:
        """Test that AWS_DEFAULT_REGION is used when no CLI argument provided."""
        # Set up environment
        os.environ["LOGAI_ANTHROPIC_API_KEY"] = "sk-ant-test-key"
        os.environ["AWS_DEFAULT_REGION"] = "us-west-2"
        os.environ["AWS_ACCESS_KEY_ID"] = "AKIATEST"
        os.environ["AWS_SECRET_ACCESS_KEY"] = "secrettest"

        with patch("sys.argv", ["logai"]):
            with patch("logai.cli.get_settings") as mock_get_settings:
                from logai.config import LogAISettings

                settings = LogAISettings()  # type: ignore
                mock_get_settings.return_value = settings

                with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                    with patch("logai.cli.LogAIApp") as mock_app:
                        mock_app.return_value.run.return_value = None
                        result = main()

                # Check that environment variable was used
                assert settings.aws_region == "us-west-2"
                assert result == 0

                # Check that startup output mentions environment
                output = mock_stdout.getvalue()
                assert "environment/default" in output
                assert "us-west-2" in output


class TestCombinedAWSArguments:
    """Test suite for combined --aws-profile and --aws-region arguments."""

    @pytest.fixture
    def mock_components(self) -> None:
        """Mock all components to avoid actual initialization."""
        with (
            patch("logai.cli.CloudWatchDataSource"),
            patch("logai.cli.LogSanitizer"),
            patch("logai.cli.CacheManager"),
            patch("logai.cli.ToolRegistry"),
            patch("logai.cli.LiteLLMProvider"),
            patch("logai.cli.LLMOrchestrator"),
            patch("logai.cli.LogAIApp"),
        ):
            yield

    def test_both_profile_and_region_via_cli(self, clean_env: None, mock_components: None) -> None:
        """Test that both --aws-profile and --aws-region work together."""
        # Set up environment with different values
        os.environ["LOGAI_ANTHROPIC_API_KEY"] = "sk-ant-test-key"
        os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
        os.environ["AWS_PROFILE"] = "env-profile"
        os.environ["AWS_ACCESS_KEY_ID"] = "AKIATEST"
        os.environ["AWS_SECRET_ACCESS_KEY"] = "secrettest"

        with patch(
            "sys.argv", ["logai", "--aws-profile", "cli-profile", "--aws-region", "ap-southeast-2"]
        ):
            with patch("logai.cli.get_settings") as mock_get_settings:
                from logai.config import LogAISettings

                settings = LogAISettings()  # type: ignore
                mock_get_settings.return_value = settings

                with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                    with patch("logai.cli.LogAIApp") as mock_app:
                        mock_app.return_value.run.return_value = None
                        result = main()

                # Check that both CLI arguments were applied
                assert settings.aws_profile == "cli-profile"
                assert settings.aws_region == "ap-southeast-2"
                assert result == 0

                # Check startup output
                output = mock_stdout.getvalue()
                assert "cli-profile" in output
                assert "ap-southeast-2" in output
                assert output.count("CLI argument") == 2  # Both from CLI


class TestCLIPrecedenceOrder:
    """Test suite for validating precedence order: CLI > env > default."""

    @pytest.fixture
    def mock_components(self) -> None:
        """Mock all components to avoid actual initialization."""
        with (
            patch("logai.cli.CloudWatchDataSource"),
            patch("logai.cli.LogSanitizer"),
            patch("logai.cli.CacheManager"),
            patch("logai.cli.ToolRegistry"),
            patch("logai.cli.LiteLLMProvider"),
            patch("logai.cli.LLMOrchestrator"),
            patch("logai.cli.LogAIApp"),
        ):
            yield

    def test_precedence_cli_over_env(self, clean_env: None, mock_components: None) -> None:
        """Test precedence: CLI argument takes priority over environment variable."""
        # Set environment variables
        os.environ["LOGAI_ANTHROPIC_API_KEY"] = "sk-ant-test-key"
        os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
        os.environ["AWS_PROFILE"] = "env-profile"
        os.environ["AWS_ACCESS_KEY_ID"] = "AKIATEST"
        os.environ["AWS_SECRET_ACCESS_KEY"] = "secrettest"

        with patch(
            "sys.argv", ["logai", "--aws-profile", "cli-profile", "--aws-region", "us-west-2"]
        ):
            with patch("logai.cli.get_settings") as mock_get_settings:
                from logai.config import LogAISettings

                settings = LogAISettings()  # type: ignore
                mock_get_settings.return_value = settings

                with patch("sys.stdout", new_callable=StringIO):
                    with patch("logai.cli.LogAIApp") as mock_app:
                        mock_app.return_value.run.return_value = None
                        main()

                # CLI values should override environment values
                assert settings.aws_profile == "cli-profile"  # not env-profile
                assert settings.aws_region == "us-west-2"  # not us-east-1

    def test_precedence_env_when_no_cli(self, clean_env: None, mock_components: None) -> None:
        """Test that environment variables are used when CLI arguments not provided."""
        # Set environment variables
        os.environ["LOGAI_ANTHROPIC_API_KEY"] = "sk-ant-test-key"
        os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
        os.environ["AWS_PROFILE"] = "env-profile"
        os.environ["AWS_ACCESS_KEY_ID"] = "AKIATEST"
        os.environ["AWS_SECRET_ACCESS_KEY"] = "secrettest"

        with patch("sys.argv", ["logai"]):  # No CLI args
            with patch("logai.cli.get_settings") as mock_get_settings:
                from logai.config import LogAISettings

                settings = LogAISettings()  # type: ignore
                mock_get_settings.return_value = settings

                with patch("sys.stdout", new_callable=StringIO):
                    with patch("logai.cli.LogAIApp") as mock_app:
                        mock_app.return_value.run.return_value = None
                        main()

                # Environment values should be used
                assert settings.aws_profile == "env-profile"
                assert settings.aws_region == "us-east-1"


class TestLoggingSetup:
    """Test suite for setup_logging() to verify correct handler configuration."""

    @pytest.fixture(autouse=True)
    def cleanup_logging(self):
        """Clean up logging handlers after each test to avoid interference."""
        logging.getLogger().handlers.clear()
        logging.getLogger().setLevel(logging.WARNING)
        yield
        logging.getLogger().handlers.clear()
        logging.getLogger().setLevel(logging.WARNING)

    def _app_handlers(self) -> list[logging.Handler]:
        """Return handlers added by our app, filtering out pytest's internal handlers."""
        return [
            h
            for h in logging.getLogger().handlers
            if type(h).__name__
            not in ["LogCaptureHandler", "_LiveLoggingNullHandler", "_FileHandler"]
        ]

    def test_file_handler_only_when_file_succeeds(self, tmp_path):
        """StreamHandler is NOT added when file logging succeeds (protects TUI)."""
        from logai.cli import setup_logging

        log_file = tmp_path / "test.log"
        setup_logging(cli_level="INFO", settings=None, log_file=str(log_file))

        app_handlers = self._app_handlers()

        assert len(app_handlers) == 1, (
            f"Expected exactly 1 app handler (FileHandler), but found {len(app_handlers)}. "
            f"Handlers: {[type(h).__name__ for h in app_handlers]}"
        )
        assert isinstance(
            app_handlers[0], logging.FileHandler
        ), f"Expected FileHandler, but got {type(app_handlers[0]).__name__}"

        # No bare StreamHandler — that would corrupt the TUI
        stream_handlers = [
            h
            for h in app_handlers
            if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
        ]
        assert len(stream_handlers) == 0, (
            f"Expected NO StreamHandler, but found {len(stream_handlers)}. "
            "Debug logs would appear in the TUI!"
        )

        assert log_file.exists(), "Log file should have been created"

    def test_console_fallback_when_file_fails(self):
        """StreamHandler IS added as emergency fallback when file logging fails."""
        from logai.cli import setup_logging

        captured_stderr = io.StringIO()
        with patch("sys.stderr", captured_stderr):
            setup_logging(
                cli_level="INFO",
                settings=None,
                log_file="/root/cannot/write/here/test.log",
            )

        app_handlers = self._app_handlers()

        assert len(app_handlers) == 1, (
            f"Expected exactly 1 app handler (StreamHandler), but found {len(app_handlers)}. "
            f"Handlers: {[type(h).__name__ for h in app_handlers]}"
        )
        assert isinstance(
            app_handlers[0], logging.StreamHandler
        ), f"Expected StreamHandler, but got {type(app_handlers[0]).__name__}"
        assert not isinstance(
            app_handlers[0], logging.FileHandler
        ), "Handler should be StreamHandler, not FileHandler"

        stderr_output = captured_stderr.getvalue()
        assert (
            "Warning: Could not create log file" in stderr_output
        ), "Expected warning message about failed file logging"
        assert "Logging to console only" in stderr_output, "Expected message about console fallback"

    def test_default_log_file_location(self):
        """Default log file resolves to ~/.logai/logs/logai.log."""
        from logai.cli import setup_logging

        setup_logging(cli_level=None, settings=None, log_file=None)

        app_handlers = self._app_handlers()

        assert len(app_handlers) == 1
        assert isinstance(app_handlers[0], logging.FileHandler)

        expected_path = Path.home() / ".logai" / "logs" / "logai.log"
        assert (
            Path(app_handlers[0].baseFilename) == expected_path
        ), f"Expected log file at {expected_path}, but got {app_handlers[0].baseFilename}"

    def test_creates_parent_directories(self, tmp_path):
        """Parent directories are created automatically when they don't exist."""
        from logai.cli import setup_logging

        log_file = tmp_path / "nested" / "deep" / "logs" / "test.log"
        assert not log_file.parent.exists(), "Parent directory should not exist yet"

        setup_logging(cli_level=None, settings=None, log_file=str(log_file))

        assert log_file.parent.exists(), "Parent directories should have been created"
        assert log_file.exists(), "Log file should have been created"

        app_handlers = self._app_handlers()
        assert len(app_handlers) == 1
        assert isinstance(app_handlers[0], logging.FileHandler)

    def test_format_includes_required_fields(self, tmp_path):
        """Log format includes timestamp, logger name, level, and message."""
        from logai.cli import setup_logging

        log_file = tmp_path / "test.log"
        setup_logging(cli_level="INFO", settings=None, log_file=str(log_file))

        test_logger = logging.getLogger("test_module")
        test_logger.info("Test message")

        for handler in self._app_handlers():
            handler.flush()

        log_content = log_file.read_text()

        assert "test_module" in log_content, "Log should include logger name"
        assert "INFO" in log_content, "Log should include log level"
        assert "Test message" in log_content, "Log should include message"

        import re

        timestamp_pattern = r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}"
        assert re.search(timestamp_pattern, log_content), "Log should include timestamp"


class TestLogLevelPrecedence:
    """Test suite for log level resolution in setup_logging()."""

    @pytest.fixture(autouse=True)
    def cleanup_logging(self):
        """Clean up logging handlers after each test to avoid interference."""
        logging.getLogger().handlers.clear()
        logging.getLogger().setLevel(logging.WARNING)
        yield
        logging.getLogger().handlers.clear()
        logging.getLogger().setLevel(logging.WARNING)

    def test_cli_level_overrides_settings(self, tmp_path, clean_env):
        """CLI --loglevel takes highest precedence over settings.log_level."""
        from logai.cli import setup_logging
        from logai.config import LogAISettings

        os.environ["LOGAI_LOG_LEVEL"] = "INFO"
        os.environ["LOGAI_ANTHROPIC_API_KEY"] = "sk-test"
        os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
        settings = LogAISettings()  # type: ignore

        setup_logging(
            cli_level="DEBUG",
            settings=settings,
            log_file=str(tmp_path / "test.log"),
        )

        assert logging.getLogger().level == logging.DEBUG

    def test_settings_used_when_no_cli_level(self, tmp_path, clean_env):
        """settings.log_level (from LOGAI_LOG_LEVEL / .env) is used when CLI flag absent."""
        from logai.cli import setup_logging
        from logai.config import LogAISettings

        os.environ["LOGAI_LOG_LEVEL"] = "ERROR"
        os.environ["LOGAI_ANTHROPIC_API_KEY"] = "sk-test"
        os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
        settings = LogAISettings()  # type: ignore

        setup_logging(
            cli_level=None,
            settings=settings,
            log_file=str(tmp_path / "test.log"),
        )

        assert logging.getLogger().level == logging.ERROR

    def test_default_level_when_nothing_set(self, tmp_path, clean_env):
        """Default is WARNING when neither CLI flag nor env var is set."""
        from logai.cli import setup_logging

        setup_logging(
            cli_level=None,
            settings=None,
            log_file=str(tmp_path / "test.log"),
        )

        assert logging.getLogger().level == logging.WARNING

    def test_default_level_constant_is_warning(self, tmp_path, clean_env):
        """DEFAULT_LOG_LEVEL constant is WARNING (not the old INFO default)."""
        from logai.cli import DEFAULT_LOG_LEVEL, setup_logging

        assert DEFAULT_LOG_LEVEL == "WARNING"

        setup_logging(
            cli_level=None,
            settings=None,
            log_file=str(tmp_path / "test.log"),
        )

        assert logging.getLogger().level == logging.WARNING

    def test_cli_warning_overrides_env_debug(self, tmp_path, clean_env):
        """CLI WARNING takes precedence even when LOGAI_LOG_LEVEL=DEBUG in env."""
        from logai.cli import setup_logging
        from logai.config import LogAISettings

        os.environ["LOGAI_LOG_LEVEL"] = "DEBUG"
        os.environ["LOGAI_ANTHROPIC_API_KEY"] = "sk-test"
        os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
        settings = LogAISettings()  # type: ignore

        setup_logging(
            cli_level="WARNING",
            settings=settings,
            log_file=str(tmp_path / "test.log"),
        )

        assert logging.getLogger().level == logging.WARNING

    def test_settings_none_falls_back_to_default(self, tmp_path, clean_env):
        """When settings is None and no CLI flag, falls back to WARNING default."""
        from logai.cli import setup_logging

        setup_logging(
            cli_level=None,
            settings=None,
            log_file=str(tmp_path / "test.log"),
        )

        assert logging.getLogger().level == logging.WARNING


class TestLogLevelCLIArgument:
    """Test suite for --loglevel argument parsing via _build_parser()."""

    def test_loglevel_debug_accepted(self):
        """--loglevel DEBUG is accepted and stored on args."""
        from logai.cli import _build_parser

        with patch("sys.argv", ["logai", "--loglevel", "DEBUG"]):
            parser = _build_parser()
            args = parser.parse_args()
            assert args.loglevel == "DEBUG"

    def test_loglevel_case_insensitive(self):
        """--loglevel debug (lowercase) is normalised to DEBUG."""
        from logai.cli import _build_parser

        with patch("sys.argv", ["logai", "--loglevel", "debug"]):
            parser = _build_parser()
            args = parser.parse_args()
            assert args.loglevel == "DEBUG"

    def test_loglevel_all_valid_levels_accepted(self):
        """All four valid levels are accepted."""
        from logai.cli import _build_parser

        for level in ("DEBUG", "INFO", "WARNING", "ERROR"):
            with patch("sys.argv", ["logai", "--loglevel", level]):
                parser = _build_parser()
                args = parser.parse_args()
                assert args.loglevel == level

    def test_loglevel_default_is_none(self):
        """When --loglevel is omitted, args.loglevel is None (enables precedence logic)."""
        from logai.cli import _build_parser

        with patch("sys.argv", ["logai"]):
            parser = _build_parser()
            args = parser.parse_args()
            assert args.loglevel is None

    def test_loglevel_invalid_rejected(self):
        """Invalid level (e.g. TRACE) is rejected by argparse."""
        from logai.cli import _build_parser

        with patch("sys.argv", ["logai", "--loglevel", "TRACE"]):
            parser = _build_parser()
            with pytest.raises(SystemExit):
                parser.parse_args()

    def test_debug_flag_gives_clear_error(self):
        """--debug gives a clear migration error pointing to --loglevel DEBUG."""
        from logai.cli import _build_parser

        with patch("sys.argv", ["logai", "--debug"]):
            parser = _build_parser()
            with pytest.raises(SystemExit):
                parser.parse_args()


class TestLogLevelIntegration:
    """Integration tests verifying the full CLI → setup_logging() log level flow."""

    @pytest.fixture(autouse=True)
    def cleanup_logging(self):
        """Clean up logging handlers after each test to avoid interference."""
        logging.getLogger().handlers.clear()
        logging.getLogger().setLevel(logging.WARNING)
        yield
        logging.getLogger().handlers.clear()
        logging.getLogger().setLevel(logging.WARNING)

    def test_loglevel_debug_captures_all_messages(self, tmp_path, clean_env):
        """--loglevel DEBUG → DEBUG, INFO, and WARNING messages all appear in log file."""
        from logai.cli import setup_logging

        log_file = tmp_path / "test.log"
        setup_logging(cli_level="DEBUG", settings=None, log_file=str(log_file))

        test_logger = logging.getLogger("test.integration")
        test_logger.debug("debug message")
        test_logger.info("info message")
        test_logger.warning("warning message")

        for h in logging.getLogger().handlers:
            h.flush()

        content = log_file.read_text()
        assert "debug message" in content
        assert "info message" in content
        assert "warning message" in content

    def test_loglevel_warning_hides_debug_and_info(self, tmp_path, clean_env):
        """--loglevel WARNING → DEBUG and INFO messages are suppressed."""
        from logai.cli import setup_logging

        log_file = tmp_path / "test.log"
        setup_logging(cli_level="WARNING", settings=None, log_file=str(log_file))

        test_logger = logging.getLogger("test.integration")
        test_logger.debug("should not appear")
        test_logger.info("should not appear")
        test_logger.warning("should appear")

        for h in logging.getLogger().handlers:
            h.flush()

        content = log_file.read_text()
        assert "should not appear" not in content
        assert "should appear" in content
