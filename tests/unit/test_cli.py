"""Tests for CLI argument parsing and settings override."""

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
                with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
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
