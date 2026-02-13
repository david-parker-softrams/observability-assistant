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
    """Test suite for setup_logging() to verify no console handler when file logging succeeds."""

    @pytest.fixture(autouse=True)
    def cleanup_logging(self):
        """Clean up logging handlers after each test to avoid interference."""
        # Clear existing handlers before test
        logging.getLogger().handlers.clear()
        logging.getLogger().setLevel(logging.WARNING)

        yield

        # Clear handlers after test
        logging.getLogger().handlers.clear()
        logging.getLogger().setLevel(logging.WARNING)

    @pytest.mark.parametrize("level", [False, True])
    def test_setup_logging_no_console_handler_when_file_succeeds(self, tmp_path, level):
        """Test that StreamHandler is NOT added when file logging succeeds.

        This test verifies Jackie's fix: StreamHandler should only be added when
        file logging fails, not unconditionally. This prevents debug logs from
        appearing in the TUI.

        Args:
            tmp_path: pytest fixture for temporary directory
            level: False for INFO, True for DEBUG
        """
        from logai.cli import setup_logging

        log_file = tmp_path / "test.log"

        # Call setup_logging with valid file path
        setup_logging(
            debug=level,
            log_file=str(log_file),
        )

        root_logger = logging.getLogger()

        # Filter out pytest's own handlers (LogCaptureHandler, _LiveLoggingNullHandler)
        app_handlers = [
            h
            for h in root_logger.handlers
            if type(h).__name__
            not in ["LogCaptureHandler", "_LiveLoggingNullHandler", "_FileHandler"]
        ]

        # Should have exactly ONE handler from our app (FileHandler)
        assert len(app_handlers) == 1, (
            f"Expected exactly 1 app handler (FileHandler), but found {len(app_handlers)}. "
            f"Handlers: {[type(h).__name__ for h in app_handlers]}"
        )
        assert isinstance(
            app_handlers[0], logging.FileHandler
        ), f"Expected FileHandler, but got {type(app_handlers[0]).__name__}"

        # Should NOT have StreamHandler (excluding FileHandler which is a subclass)
        stream_handlers = [
            h
            for h in app_handlers
            if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
        ]
        assert len(stream_handlers) == 0, (
            f"Expected NO StreamHandler, but found {len(stream_handlers)}. "
            f"This means debug logs will appear in the TUI!"
        )

        # Verify log file was created
        assert log_file.exists(), "Log file should have been created"

        # Verify correct log level
        expected_level = logging.DEBUG if level else logging.INFO
        assert root_logger.level == expected_level, (
            f"Expected log level {logging.getLevelName(expected_level)}, "
            f"but got {logging.getLevelName(root_logger.level)}"
        )

    @pytest.mark.parametrize("level", [False, True])
    def test_setup_logging_console_handler_when_file_fails(self, level):
        """Test that StreamHandler IS added when file logging fails.

        This test verifies the fallback behavior: when file logging fails,
        a StreamHandler should be added as a fallback to ensure logs are
        not lost.

        Args:
            level: False for INFO, True for DEBUG
        """
        from logai.cli import setup_logging

        # Use invalid path to force file logging to fail
        # /root typically requires elevated permissions
        invalid_path = "/root/cannot/write/here/test.log"

        # Capture stderr to verify warning message
        captured_stderr = io.StringIO()

        with patch("sys.stderr", captured_stderr):
            setup_logging(
                debug=level,
                log_file=invalid_path,
            )

        root_logger = logging.getLogger()

        # Filter out pytest's own handlers
        app_handlers = [
            h
            for h in root_logger.handlers
            if type(h).__name__
            not in ["LogCaptureHandler", "_LiveLoggingNullHandler", "_FileHandler"]
        ]

        # Should have exactly ONE handler from our app (StreamHandler as fallback)
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

        # Verify warning message was printed to stderr
        stderr_output = captured_stderr.getvalue()
        assert (
            "Warning: Could not create log file" in stderr_output
        ), "Expected warning message about failed file logging"
        assert "Logging to console only" in stderr_output, "Expected message about console fallback"

        # Verify correct log level
        expected_level = logging.DEBUG if level else logging.INFO
        assert root_logger.level == expected_level, (
            f"Expected log level {logging.getLevelName(expected_level)}, "
            f"but got {logging.getLevelName(root_logger.level)}"
        )

    def test_setup_logging_default_log_file_location(self):
        """Test that default log file location is ~/.logai/logs/logai.log."""
        from logai.cli import setup_logging

        # Call without specifying log_file
        setup_logging(debug=False, log_file=None)

        root_logger = logging.getLogger()

        # Filter out pytest's own handlers
        app_handlers = [
            h
            for h in root_logger.handlers
            if type(h).__name__
            not in ["LogCaptureHandler", "_LiveLoggingNullHandler", "_FileHandler"]
        ]

        # Should have exactly ONE handler from our app
        assert len(app_handlers) == 1
        assert isinstance(app_handlers[0], logging.FileHandler)

        # Verify the log file path
        handler = app_handlers[0]
        expected_path = Path.home() / ".logai" / "logs" / "logai.log"
        assert (
            Path(handler.baseFilename) == expected_path
        ), f"Expected log file at {expected_path}, but got {handler.baseFilename}"

    def test_setup_logging_creates_parent_directories(self, tmp_path):
        """Test that setup_logging creates parent directories if they don't exist."""
        from logai.cli import setup_logging

        # Use a nested path that doesn't exist yet
        log_file = tmp_path / "nested" / "deep" / "logs" / "test.log"
        assert not log_file.parent.exists(), "Parent directory should not exist yet"

        setup_logging(debug=False, log_file=str(log_file))

        # Verify parent directories were created
        assert log_file.parent.exists(), "Parent directories should have been created"
        assert log_file.exists(), "Log file should have been created"

        # Verify correct handler type
        root_logger = logging.getLogger()
        app_handlers = [
            h
            for h in root_logger.handlers
            if type(h).__name__
            not in ["LogCaptureHandler", "_LiveLoggingNullHandler", "_FileHandler"]
        ]

        assert len(app_handlers) == 1
        assert isinstance(app_handlers[0], logging.FileHandler)

    def test_setup_logging_format_includes_required_fields(self, tmp_path):
        """Test that log format includes timestamp, name, level, and message."""
        from logai.cli import setup_logging

        log_file = tmp_path / "test.log"
        setup_logging(debug=False, log_file=str(log_file))

        # Get the file handler to ensure logs go to the file
        root_logger = logging.getLogger()
        app_handlers = [
            h
            for h in root_logger.handlers
            if type(h).__name__
            not in ["LogCaptureHandler", "_LiveLoggingNullHandler", "_FileHandler"]
        ]

        # Write a test log message
        test_logger = logging.getLogger("test_module")
        test_logger.info("Test message")

        # Flush the handler to ensure data is written
        for handler in app_handlers:
            handler.flush()

        # Read the log file
        log_content = log_file.read_text()

        # Verify format includes required components
        assert "test_module" in log_content, "Log should include logger name"
        assert "INFO" in log_content, "Log should include log level"
        assert "Test message" in log_content, "Log should include message"
        # Check for timestamp pattern (YYYY-MM-DD HH:MM:SS)
        import re

        timestamp_pattern = r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}"
        assert re.search(timestamp_pattern, log_content), "Log should include timestamp"
