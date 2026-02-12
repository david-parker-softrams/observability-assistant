# Architecture Document: GitHub Copilot Integration for LogAI

**Document Version:** 1.0  
**Author:** Sally (Senior Software Architect)  
**Date:** February 11, 2026  
**Status:** Ready for Implementation

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [System Overview](#2-system-overview)
3. [Component Design](#3-component-design)
4. [Data Flow Diagrams](#4-data-flow-diagrams)
5. [File Structure](#5-file-structure)
6. [Security Considerations](#6-security-considerations)
7. [API Integration Details](#7-api-integration-details)
8. [Configuration Examples](#8-configuration-examples)
9. [Compatibility Considerations](#9-compatibility-considerations)
10. [Testing Strategy](#10-testing-strategy)
11. [Implementation Phases](#11-implementation-phases)
12. [Migration and Rollout](#12-migration-and-rollout)
13. [Appendices](#13-appendices)

---

## 1. Executive Summary

### 1.1 Purpose

This document provides a comprehensive architecture design for integrating GitHub Copilot support into LogAI. The integration enables LogAI users to authenticate with GitHub Copilot and access 24+ LLM models (Claude, GPT, Gemini, Grok) through GitHub's unified API.

### 1.2 Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Authentication Flow** | OAuth 2.0 Device Code Flow | Standard GitHub auth, works in terminal environments |
| **Token Storage** | Secure file-based with fallback to keyring | Balance of simplicity and security |
| **Provider Integration** | New dedicated provider class | Clean separation, doesn't pollute LiteLLM provider |
| **CLI Framework** | Extend existing argparse with subcommands | Consistency with current LogAI patterns |
| **Configuration** | Extend existing `LogAISettings` | Single source of truth for all settings |
| **File Permissions** | 600 (owner-only) | Security improvement over OpenCode's 644 |

### 1.3 Estimated Complexity

**Overall: Moderate**

- Authentication Module: Moderate (OAuth device code flow implementation)
- Provider Integration: Simple (follows existing patterns)
- CLI Commands: Simple (extend existing patterns)
- Security Hardening: Moderate (encryption, permissions)
- Testing: Moderate (mock auth flows)

---

## 2. System Overview

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              LogAI Application                                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐           │
│  │    CLI Layer     │    │    TUI Layer     │    │  Orchestrator    │           │
│  │  (cli.py + auth) │    │   (app.py)       │    │                  │           │
│  └────────┬─────────┘    └────────┬─────────┘    └────────┬─────────┘           │
│           │                       │                       │                      │
│           └───────────────────────┼───────────────────────┘                      │
│                                   │                                              │
│                    ┌──────────────▼──────────────┐                               │
│                    │      Provider Factory       │                               │
│                    │   (selects LLM provider)    │                               │
│                    └──────────────┬──────────────┘                               │
│                                   │                                              │
│         ┌─────────────────────────┼─────────────────────────┐                    │
│         │                         │                         │                    │
│   ┌─────▼─────┐            ┌──────▼──────┐           ┌──────▼──────┐            │
│   │  LiteLLM  │            │   GitHub    │           │   Future    │            │
│   │  Provider │            │   Copilot   │           │  Providers  │            │
│   │           │            │   Provider  │           │             │            │
│   │ • Anthropic│           │   (NEW)     │           │             │            │
│   │ • OpenAI   │           │             │           │             │            │
│   │ • Ollama   │           │             │           │             │            │
│   └─────┬─────┘            └──────┬──────┘           └─────────────┘            │
│         │                         │                                              │
│         │                  ┌──────▼──────┐                                       │
│         │                  │    Auth     │                                       │
│         │                  │   Manager   │                                       │
│         │                  │   (NEW)     │                                       │
│         │                  └──────┬──────┘                                       │
│         │                         │                                              │
└─────────┼─────────────────────────┼──────────────────────────────────────────────┘
          │                         │
          ▼                         ▼
┌──────────────────┐      ┌──────────────────┐      ┌──────────────────┐
│ Anthropic/OpenAI │      │ GitHub Copilot   │      │ ~/.local/share/  │
│      APIs        │      │       API        │      │   logai/auth.json│
│                  │      │                  │      │   (Credentials)  │
└──────────────────┘      └──────────────────┘      └──────────────────┘
```

### 2.2 Integration Points with Current LogAI

| Component | Current State | Integration Approach |
|-----------|---------------|---------------------|
| `src/logai/providers/llm/base.py` | Defines `BaseLLMProvider` | GitHub Copilot provider inherits from this |
| `src/logai/providers/llm/litellm_provider.py` | Handles Anthropic, OpenAI, Ollama | Add `github_copilot` to `from_settings()` |
| `src/logai/config/settings.py` | `LogAISettings` with Pydantic | Add GitHub Copilot configuration fields |
| `src/logai/cli.py` | Uses argparse | Add `auth` subcommand group |
| `tests/unit/test_llm_provider.py` | Tests for LiteLLM provider | Add parallel tests for GitHub Copilot |

### 2.3 Design Principles Applied

1. **Security First**: Token storage with 600 permissions, optional keyring integration
2. **Consistency**: Follow existing LogAI patterns for providers, settings, CLI
3. **Simplicity**: Single `logai auth login` command initiates authentication
4. **Testability**: Mock-friendly auth manager, injectable dependencies
5. **Flexibility**: Support for future auth providers and methods

---

## 3. Component Design

### 3.1 Authentication Manager

**File:** `src/logai/auth/github_copilot_auth.py`

```python
"""GitHub Copilot OAuth authentication manager."""

from __future__ import annotations

import json
import os
import stat
import time
import webbrowser
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from logai.config.settings import LogAISettings


@dataclass
class OAuthCredentials:
    """OAuth credentials for GitHub Copilot."""
    
    type: str = "oauth"
    access_token: str = ""
    refresh_token: str = ""
    expires_at: int = 0  # Unix timestamp, 0 = no expiration
    token_type: str = "bearer"
    
    def is_valid(self) -> bool:
        """Check if credentials are valid and not expired."""
        if not self.access_token:
            return False
        if self.expires_at == 0:
            return True  # No expiration
        return time.time() < self.expires_at
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "type": self.type,
            "access": self.access_token,
            "refresh": self.refresh_token,
            "expires": self.expires_at,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OAuthCredentials:
        """Create from dictionary."""
        return cls(
            type=data.get("type", "oauth"),
            access_token=data.get("access", ""),
            refresh_token=data.get("refresh", ""),
            expires_at=data.get("expires", 0),
        )


@dataclass
class DeviceCodeResponse:
    """Response from GitHub device code request."""
    
    device_code: str
    user_code: str
    verification_uri: str
    expires_in: int
    interval: int


class GitHubCopilotAuthError(Exception):
    """Base exception for GitHub Copilot authentication errors."""
    pass


class AuthenticationTimeoutError(GitHubCopilotAuthError):
    """Raised when authentication times out."""
    pass


class AuthenticationDeniedError(GitHubCopilotAuthError):
    """Raised when user denies authentication."""
    pass


class GitHubCopilotAuthManager:
    """
    Manages GitHub Copilot OAuth authentication.
    
    Uses OAuth 2.0 Device Authorization Grant (RFC 8628) for terminal-based
    authentication without requiring a callback URL.
    
    Credentials are stored in:
      - Primary: ~/.local/share/logai/auth.json (with 600 permissions)
      - Fallback: keyring (if available and configured)
      - Override: LOGAI_GITHUB_COPILOT_TOKEN environment variable
    """
    
    # GitHub OAuth endpoints
    DEVICE_CODE_URL = "https://github.com/login/device/code"
    TOKEN_URL = "https://github.com/login/oauth/access_token"
    
    # GitHub Copilot OAuth client ID (public, not secret)
    # This is the client ID used by VS Code/OpenCode for Copilot
    CLIENT_ID = "Iv1.b507a08c87ecfe98"
    
    # OAuth scopes required for Copilot access
    SCOPES = "read:user"
    
    def __init__(
        self,
        settings: LogAISettings | None = None,
        auth_file_path: Path | None = None,
    ):
        """
        Initialize authentication manager.
        
        Args:
            settings: LogAI settings instance
            auth_file_path: Override path for auth file (for testing)
        """
        self._settings = settings
        self._credentials: OAuthCredentials | None = None
        self._http_client: httpx.Client | None = None
        
        # Determine auth file path
        if auth_file_path:
            self._auth_file = auth_file_path
        else:
            # XDG Base Directory compliant
            xdg_data_home = os.environ.get(
                "XDG_DATA_HOME",
                str(Path.home() / ".local" / "share")
            )
            self._auth_file = Path(xdg_data_home) / "logai" / "auth.json"
    
    @property
    def http_client(self) -> httpx.Client:
        """Lazy-initialized HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.Client(
                timeout=30.0,
                headers={"Accept": "application/json"},
            )
        return self._http_client
    
    def close(self) -> None:
        """Close HTTP client."""
        if self._http_client:
            self._http_client.close()
            self._http_client = None
    
    def __enter__(self) -> GitHubCopilotAuthManager:
        return self
    
    def __exit__(self, *args: Any) -> None:
        self.close()
    
    # ─────────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────────
    
    def is_authenticated(self) -> bool:
        """Check if user is authenticated with valid credentials."""
        creds = self.get_credentials()
        return creds is not None and creds.is_valid()
    
    def get_token(self) -> str | None:
        """
        Get the current access token.
        
        Priority:
        1. Environment variable LOGAI_GITHUB_COPILOT_TOKEN
        2. Cached credentials
        3. File-based credentials
        
        Returns:
            Access token or None if not authenticated
        """
        # Check environment variable first
        env_token = os.environ.get("LOGAI_GITHUB_COPILOT_TOKEN")
        if env_token:
            return env_token
        
        creds = self.get_credentials()
        if creds and creds.is_valid():
            return creds.access_token
        return None
    
    def get_credentials(self) -> OAuthCredentials | None:
        """Load and return credentials."""
        if self._credentials is None:
            self._credentials = self._load_credentials()
        return self._credentials
    
    def login(
        self,
        open_browser: bool = True,
        timeout: int = 300,
    ) -> OAuthCredentials:
        """
        Initiate OAuth device code flow for GitHub Copilot.
        
        Args:
            open_browser: Automatically open browser for authentication
            timeout: Maximum time to wait for authentication (seconds)
        
        Returns:
            OAuth credentials on successful authentication
        
        Raises:
            AuthenticationTimeoutError: If authentication times out
            AuthenticationDeniedError: If user denies access
            GitHubCopilotAuthError: For other authentication errors
        """
        # Step 1: Request device code
        device_code_response = self._request_device_code()
        
        # Step 2: Display user code and instructions
        print("\n" + "=" * 60)
        print("GitHub Copilot Authentication")
        print("=" * 60)
        print(f"\n1. Open: {device_code_response.verification_uri}")
        print(f"2. Enter code: {device_code_response.user_code}")
        print("\nWaiting for authentication...")
        
        if open_browser:
            try:
                webbrowser.open(device_code_response.verification_uri)
            except Exception:
                pass  # Browser opening is best-effort
        
        # Step 3: Poll for token
        credentials = self._poll_for_token(
            device_code=device_code_response.device_code,
            interval=device_code_response.interval,
            expires_in=min(device_code_response.expires_in, timeout),
        )
        
        # Step 4: Save credentials
        self._save_credentials(credentials)
        self._credentials = credentials
        
        print("\n✓ Authentication successful!")
        return credentials
    
    def logout(self) -> bool:
        """
        Remove stored credentials.
        
        Returns:
            True if credentials were removed, False if none existed
        """
        self._credentials = None
        
        if self._auth_file.exists():
            # Load existing auth file
            try:
                with open(self._auth_file, "r") as f:
                    auth_data = json.load(f)
            except (json.JSONDecodeError, OSError):
                auth_data = {}
            
            # Remove github-copilot credentials
            if "github-copilot" in auth_data:
                del auth_data["github-copilot"]
                
                if auth_data:
                    # Other providers exist, keep file
                    self._write_auth_file(auth_data)
                else:
                    # No other providers, remove file
                    self._auth_file.unlink()
                
                return True
        
        return False
    
    def get_status(self) -> dict[str, Any]:
        """
        Get authentication status information.
        
        Returns:
            Dictionary with status information
        """
        creds = self.get_credentials()
        env_token = os.environ.get("LOGAI_GITHUB_COPILOT_TOKEN")
        
        return {
            "authenticated": self.is_authenticated(),
            "source": "environment" if env_token else "file" if creds else None,
            "token_prefix": self._mask_token(self.get_token()) if self.is_authenticated() else None,
            "expires": creds.expires_at if creds else None,
            "auth_file": str(self._auth_file),
            "auth_file_exists": self._auth_file.exists(),
        }
    
    # ─────────────────────────────────────────────────────────────────────────
    # Private Methods
    # ─────────────────────────────────────────────────────────────────────────
    
    def _request_device_code(self) -> DeviceCodeResponse:
        """Request a device code from GitHub."""
        response = self.http_client.post(
            self.DEVICE_CODE_URL,
            data={
                "client_id": self.CLIENT_ID,
                "scope": self.SCOPES,
            },
        )
        
        if response.status_code != 200:
            raise GitHubCopilotAuthError(
                f"Failed to request device code: {response.status_code}"
            )
        
        data = response.json()
        return DeviceCodeResponse(
            device_code=data["device_code"],
            user_code=data["user_code"],
            verification_uri=data["verification_uri"],
            expires_in=data["expires_in"],
            interval=data.get("interval", 5),
        )
    
    def _poll_for_token(
        self,
        device_code: str,
        interval: int,
        expires_in: int,
    ) -> OAuthCredentials:
        """Poll GitHub for access token."""
        start_time = time.time()
        
        while (time.time() - start_time) < expires_in:
            time.sleep(interval)
            
            response = self.http_client.post(
                self.TOKEN_URL,
                data={
                    "client_id": self.CLIENT_ID,
                    "device_code": device_code,
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                },
            )
            
            data = response.json()
            
            if "access_token" in data:
                return OAuthCredentials(
                    access_token=data["access_token"],
                    refresh_token=data.get("refresh_token", ""),
                    expires_at=0,  # GitHub tokens don't expire by default
                    token_type=data.get("token_type", "bearer"),
                )
            
            error = data.get("error")
            if error == "authorization_pending":
                continue  # Keep polling
            elif error == "slow_down":
                interval += 5  # Back off
            elif error == "expired_token":
                raise AuthenticationTimeoutError("Device code expired")
            elif error == "access_denied":
                raise AuthenticationDeniedError("User denied access")
            else:
                raise GitHubCopilotAuthError(f"Authentication error: {error}")
        
        raise AuthenticationTimeoutError("Authentication timed out")
    
    def _load_credentials(self) -> OAuthCredentials | None:
        """Load credentials from auth file."""
        if not self._auth_file.exists():
            return None
        
        try:
            with open(self._auth_file, "r") as f:
                auth_data = json.load(f)
            
            if "github-copilot" not in auth_data:
                return None
            
            return OAuthCredentials.from_dict(auth_data["github-copilot"])
        except (json.JSONDecodeError, KeyError, OSError):
            return None
    
    def _save_credentials(self, credentials: OAuthCredentials) -> None:
        """Save credentials to auth file with secure permissions."""
        # Ensure directory exists
        self._auth_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing credentials for other providers
        if self._auth_file.exists():
            try:
                with open(self._auth_file, "r") as f:
                    auth_data = json.load(f)
            except (json.JSONDecodeError, OSError):
                auth_data = {}
        else:
            auth_data = {}
        
        # Update with new credentials
        auth_data["github-copilot"] = credentials.to_dict()
        
        self._write_auth_file(auth_data)
    
    def _write_auth_file(self, auth_data: dict[str, Any]) -> None:
        """Write auth file with secure permissions."""
        # Write to temp file first, then rename (atomic)
        temp_file = self._auth_file.with_suffix(".tmp")
        
        with open(temp_file, "w") as f:
            json.dump(auth_data, f, indent=2)
        
        # Set secure permissions (600 = owner read/write only)
        os.chmod(temp_file, stat.S_IRUSR | stat.S_IWUSR)
        
        # Atomic rename
        temp_file.rename(self._auth_file)
    
    def _mask_token(self, token: str | None) -> str | None:
        """Mask token for display (show prefix only)."""
        if not token:
            return None
        if len(token) > 10:
            return f"{token[:10]}..."
        return "***"
```

### 3.2 GitHub Copilot Provider

**File:** `src/logai/providers/llm/github_copilot_provider.py`

```python
"""GitHub Copilot LLM provider implementation."""

from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncGenerator

import httpx

from logai.auth.github_copilot_auth import (
    GitHubCopilotAuthError,
    GitHubCopilotAuthManager,
)
from logai.config.settings import LogAISettings

from .base import (
    AuthenticationError,
    BaseLLMProvider,
    InvalidRequestError,
    LLMProviderError,
    LLMResponse,
    RateLimitError,
)


# Supported GitHub Copilot models (as of Feb 2026)
GITHUB_COPILOT_MODELS = {
    # Claude models
    "claude-haiku-4.5": {"provider": "anthropic", "supports_tools": True},
    "claude-sonnet-4": {"provider": "anthropic", "supports_tools": True},
    "claude-sonnet-4.5": {"provider": "anthropic", "supports_tools": True},
    "claude-opus-4.5": {"provider": "anthropic", "supports_tools": True},
    "claude-opus-4.6": {"provider": "anthropic", "supports_tools": True},
    "claude-opus-41": {"provider": "anthropic", "supports_tools": True},
    # OpenAI models
    "gpt-4.1": {"provider": "openai", "supports_tools": True},
    "gpt-4o": {"provider": "openai", "supports_tools": True},
    "gpt-5": {"provider": "openai", "supports_tools": True},
    "gpt-5-mini": {"provider": "openai", "supports_tools": True},
    "gpt-5.1": {"provider": "openai", "supports_tools": True},
    "gpt-5.1-codex": {"provider": "openai", "supports_tools": True},
    "gpt-5.1-codex-max": {"provider": "openai", "supports_tools": True},
    "gpt-5.1-codex-mini": {"provider": "openai", "supports_tools": True},
    "gpt-5.2": {"provider": "openai", "supports_tools": True},
    "gpt-5.2-codex": {"provider": "openai", "supports_tools": True},
    # Google models
    "gemini-2.5-pro": {"provider": "google", "supports_tools": True},
    "gemini-3-flash-preview": {"provider": "google", "supports_tools": True},
    "gemini-3-pro-preview": {"provider": "google", "supports_tools": True},
    # Other
    "grok-code-fast-1": {"provider": "xai", "supports_tools": True},
}

# Default model if not specified
DEFAULT_MODEL = "claude-sonnet-4.5"


class GitHubCopilotProvider(BaseLLMProvider):
    """
    GitHub Copilot LLM provider.
    
    Provides access to 24+ models through the GitHub Copilot API,
    including Claude, GPT, Gemini, and Grok models.
    
    The API is OpenAI-compatible, making response parsing straightforward.
    
    Example:
        ```python
        provider = GitHubCopilotProvider(model="claude-sonnet-4.5")
        response = await provider.chat([
            {"role": "user", "content": "Hello!"}
        ])
        print(response.content)
        ```
    """
    
    # GitHub Copilot API endpoint
    API_ENDPOINT = "https://api.githubcopilot.com/chat/completions"
    
    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        auth_manager: GitHubCopilotAuthManager | None = None,
        settings: LogAISettings | None = None,
    ):
        """
        Initialize GitHub Copilot provider.
        
        Args:
            model: Model name (without github-copilot/ prefix)
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens to generate
            auth_manager: Optional auth manager instance (for testing)
            settings: Optional settings instance
        """
        # Strip provider prefix if present
        if model.startswith("github-copilot/"):
            model = model[len("github-copilot/"):]
        
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._settings = settings
        
        # Initialize auth manager
        self._auth_manager = auth_manager or GitHubCopilotAuthManager(settings)
        
        # HTTP client (created on first use)
        self._http_client: httpx.AsyncClient | None = None
    
    @classmethod
    def from_settings(cls, settings: LogAISettings) -> GitHubCopilotProvider:
        """
        Create provider from LogAI settings.
        
        Args:
            settings: LogAI settings instance
        
        Returns:
            Configured GitHubCopilotProvider instance
        """
        return cls(
            model=settings.github_copilot_model,
            temperature=getattr(settings, 'github_copilot_temperature', 0.7),
            max_tokens=getattr(settings, 'github_copilot_max_tokens', None),
            settings=settings,
        )
    
    @classmethod
    def get_available_models(cls) -> list[str]:
        """Get list of available models."""
        return list(GITHUB_COPILOT_MODELS.keys())
    
    @property
    def full_model_name(self) -> str:
        """Get full model name with provider prefix."""
        return f"github-copilot/{self.model}"
    
    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(60.0, connect=10.0),
            )
        return self._http_client
    
    async def close(self) -> None:
        """Close HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
    
    def _get_auth_token(self) -> str:
        """Get authentication token or raise error."""
        token = self._auth_manager.get_token()
        if not token:
            raise AuthenticationError(
                message="Not authenticated with GitHub Copilot. Run 'logai auth login' first.",
                provider="github-copilot",
                error_code="not_authenticated",
            )
        return token
    
    def _supports_tools(self) -> bool:
        """Check if current model supports tool calling."""
        model_info = GITHUB_COPILOT_MODELS.get(self.model, {})
        return model_info.get("supports_tools", False)
    
    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        stream: bool = False,
        **kwargs: Any,
    ) -> LLMResponse | AsyncGenerator[str, None]:
        """
        Send chat messages to GitHub Copilot API.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            tools: Optional tool definitions for function calling
            stream: Whether to stream the response
            **kwargs: Additional parameters (temperature, max_tokens, etc.)
        
        Returns:
            LLMResponse if not streaming, AsyncGenerator if streaming
        
        Raises:
            AuthenticationError: If not authenticated
            RateLimitError: If rate limited
            InvalidRequestError: If request is invalid
            LLMProviderError: For other errors
        """
        if stream:
            return self.stream_chat(messages=messages, tools=tools, **kwargs)
        
        try:
            token = self._get_auth_token()
            client = await self._get_http_client()
            
            # Build request body
            body: dict[str, Any] = {
                "model": self.model,
                "messages": messages,
                "temperature": kwargs.get("temperature", self.temperature),
            }
            
            if self.max_tokens:
                body["max_tokens"] = self.max_tokens
            
            # Only include tools if model supports them
            if tools and self._supports_tools():
                body["tools"] = tools
            
            # Make request
            response = await client.post(
                self.API_ENDPOINT,
                json=body,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
            
            # Handle errors
            if response.status_code != 200:
                self._handle_http_error(response)
            
            # Parse response (OpenAI-compatible format)
            data = response.json()
            return self._parse_response(data)
        
        except AuthenticationError:
            raise
        except httpx.TimeoutException as e:
            raise LLMProviderError(
                message=f"Request timed out: {e}",
                provider="github-copilot",
                error_code="timeout",
            ) from e
        except httpx.RequestError as e:
            raise LLMProviderError(
                message=f"Network error: {e}",
                provider="github-copilot",
                error_code="network_error",
            ) from e
        except Exception as e:
            if isinstance(e, LLMProviderError):
                raise
            raise LLMProviderError(
                message=f"Unexpected error: {e}",
                provider="github-copilot",
                error_code="unknown",
            ) from e
    
    async def stream_chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        """
        Stream chat response from GitHub Copilot API.
        
        Args:
            messages: List of message dictionaries
            tools: Optional tool definitions
            **kwargs: Additional parameters
        
        Yields:
            Response tokens as they arrive
        
        Raises:
            Same exceptions as chat()
        """
        try:
            token = self._get_auth_token()
            client = await self._get_http_client()
            
            # Build request body with streaming
            body: dict[str, Any] = {
                "model": self.model,
                "messages": messages,
                "temperature": kwargs.get("temperature", self.temperature),
                "stream": True,
            }
            
            if self.max_tokens:
                body["max_tokens"] = self.max_tokens
            
            if tools and self._supports_tools():
                body["tools"] = tools
            
            # Make streaming request
            async with client.stream(
                "POST",
                self.API_ENDPOINT,
                json=body,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "Accept": "text/event-stream",
                },
            ) as response:
                if response.status_code != 200:
                    # Read full response for error handling
                    await response.aread()
                    self._handle_http_error(response)
                
                # Parse SSE stream
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]  # Remove "data: " prefix
                        if data_str == "[DONE]":
                            break
                        
                        try:
                            data = json.loads(data_str)
                            if data.get("choices"):
                                delta = data["choices"][0].get("delta", {})
                                content = delta.get("content")
                                if content:
                                    yield content
                        except json.JSONDecodeError:
                            continue
        
        except AuthenticationError:
            raise
        except httpx.TimeoutException as e:
            raise LLMProviderError(
                message=f"Stream timed out: {e}",
                provider="github-copilot",
                error_code="timeout",
            ) from e
        except Exception as e:
            if isinstance(e, LLMProviderError):
                raise
            raise LLMProviderError(
                message=f"Stream error: {e}",
                provider="github-copilot",
                error_code="stream_error",
            ) from e
    
    def _parse_response(self, data: dict[str, Any]) -> LLMResponse:
        """Parse OpenAI-compatible response."""
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        
        # Extract content
        content = message.get("content")
        
        # Extract tool calls
        tool_calls = []
        if message.get("tool_calls"):
            for tc in message["tool_calls"]:
                tool_calls.append({
                    "id": tc.get("id", ""),
                    "type": tc.get("type", "function"),
                    "function": {
                        "name": tc.get("function", {}).get("name", ""),
                        "arguments": tc.get("function", {}).get("arguments", "{}"),
                    },
                })
        
        # Extract usage
        usage = {}
        if data.get("usage"):
            usage = {
                "prompt_tokens": data["usage"].get("prompt_tokens", 0),
                "completion_tokens": data["usage"].get("completion_tokens", 0),
                "total_tokens": data["usage"].get("total_tokens", 0),
            }
        
        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason=choice.get("finish_reason"),
            usage=usage,
        )
    
    def _handle_http_error(self, response: httpx.Response) -> None:
        """Handle HTTP error responses."""
        status_code = response.status_code
        
        try:
            error_data = response.json()
            error_message = error_data.get("error", {}).get("message", response.text)
        except Exception:
            error_message = response.text or f"HTTP {status_code}"
        
        # Don't leak token in error messages
        if "gho_" in error_message:
            error_message = "Authentication failed (token error)"
        
        if status_code == 401:
            raise AuthenticationError(
                message=f"Authentication failed: {error_message}",
                provider="github-copilot",
                error_code="unauthorized",
            )
        elif status_code == 429:
            raise RateLimitError(
                message=f"Rate limit exceeded: {error_message}",
                provider="github-copilot",
                error_code="rate_limit",
            )
        elif status_code == 400:
            raise InvalidRequestError(
                message=f"Invalid request: {error_message}",
                provider="github-copilot",
                error_code="bad_request",
            )
        else:
            raise LLMProviderError(
                message=f"API error ({status_code}): {error_message}",
                provider="github-copilot",
                error_code=f"http_{status_code}",
            )
```

### 3.3 Settings Extension

**Updates to:** `src/logai/config/settings.py`

```python
# Add to existing LogAISettings class:

class LogAISettings(BaseSettings):
    """Main configuration settings for LogAI application."""
    
    # ... existing fields ...
    
    # === LLM Provider Configuration ===
    llm_provider: Literal["anthropic", "openai", "ollama", "github-copilot"] = Field(
        default="anthropic",
        description="LLM provider to use",
    )
    
    # === GitHub Copilot Configuration ===
    github_copilot_model: str = Field(
        default="claude-sonnet-4.5",
        description="GitHub Copilot model to use (without provider prefix)",
    )
    
    github_copilot_temperature: float = Field(
        default=0.7,
        description="Temperature for GitHub Copilot requests",
        ge=0.0,
        le=2.0,
    )
    
    github_copilot_max_tokens: int | None = Field(
        default=None,
        description="Maximum tokens for GitHub Copilot responses",
    )
    
    # ... update validate_required_credentials method ...
    
    def validate_required_credentials(self) -> None:
        """Validate that required credentials are present based on provider selection."""
        if self.llm_provider == "anthropic":
            if not self.anthropic_api_key:
                raise ValueError(
                    "LOGAI_ANTHROPIC_API_KEY is required when using Anthropic provider"
                )
        elif self.llm_provider == "openai":
            if not self.openai_api_key:
                raise ValueError("LOGAI_OPENAI_API_KEY is required when using OpenAI provider")
        elif self.llm_provider == "ollama":
            if not self.ollama_base_url:
                raise ValueError("LOGAI_OLLAMA_BASE_URL is required when using Ollama provider")
        elif self.llm_provider == "github-copilot":
            # Credentials are validated at runtime via auth manager
            # Either auth.json or LOGAI_GITHUB_COPILOT_TOKEN must be set
            pass
        else:
            raise ValueError(f"Unsupported LLM provider: {self.llm_provider}")
        
        # ... rest of AWS validation ...
    
    @property
    def current_llm_model(self) -> str:
        """Get the model name for the currently selected LLM provider."""
        if self.llm_provider == "anthropic":
            return self.anthropic_model
        elif self.llm_provider == "openai":
            return self.openai_model
        elif self.llm_provider == "ollama":
            return self.ollama_model
        elif self.llm_provider == "github-copilot":
            return f"github-copilot/{self.github_copilot_model}"
        raise ValueError(f"Unknown LLM provider: {self.llm_provider}")
```

### 3.4 CLI Commands

**Updates to:** `src/logai/cli.py` (with new auth subcommand)

```python
"""Command-line interface for LogAI."""

import argparse
import sys
from pathlib import Path

from logai import __version__


def create_parser() -> argparse.ArgumentParser:
    """Create the main argument parser with subcommands."""
    parser = argparse.ArgumentParser(
        prog="logai",
        description="AI-powered observability assistant for AWS CloudWatch logs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    
    # Create subparsers
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # === AUTH SUBCOMMAND ===
    auth_parser = subparsers.add_parser(
        "auth",
        help="Manage authentication",
        description="Manage authentication for LLM providers",
    )
    auth_subparsers = auth_parser.add_subparsers(dest="auth_command")
    
    # auth login
    login_parser = auth_subparsers.add_parser(
        "login",
        help="Authenticate with a provider",
    )
    login_parser.add_argument(
        "provider",
        nargs="?",
        default="github-copilot",
        choices=["github-copilot"],
        help="Provider to authenticate with (default: github-copilot)",
    )
    login_parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Don't automatically open browser",
    )
    
    # auth logout
    logout_parser = auth_subparsers.add_parser(
        "logout",
        help="Remove stored credentials",
    )
    logout_parser.add_argument(
        "provider",
        nargs="?",
        default="github-copilot",
        choices=["github-copilot"],
        help="Provider to logout from (default: github-copilot)",
    )
    
    # auth status
    auth_subparsers.add_parser(
        "status",
        help="Check authentication status",
    )
    
    # auth list
    auth_subparsers.add_parser(
        "list",
        help="List available providers and models",
    )
    
    # === MODELS SUBCOMMAND ===
    models_parser = subparsers.add_parser(
        "models",
        help="List available models",
    )
    models_parser.add_argument(
        "provider",
        nargs="?",
        help="Filter by provider (e.g., github-copilot)",
    )
    
    # === RUN SUBCOMMAND (default behavior) ===
    run_parser = subparsers.add_parser(
        "run",
        help="Start LogAI TUI (default)",
    )
    _add_run_arguments(run_parser)
    
    # Add run arguments to main parser for backward compatibility
    _add_run_arguments(parser)
    
    return parser


def _add_run_arguments(parser: argparse.ArgumentParser) -> None:
    """Add run-related arguments to a parser."""
    parser.add_argument(
        "--config",
        type=Path,
        help="Path to configuration file",
        default=None,
    )
    parser.add_argument(
        "--aws-profile",
        type=str,
        help="AWS profile name",
        default=None,
        metavar="PROFILE",
    )
    parser.add_argument(
        "--aws-region",
        type=str,
        help="AWS region",
        default=None,
        metavar="REGION",
    )


def cmd_auth_login(args: argparse.Namespace) -> int:
    """Handle auth login command."""
    from logai.auth.github_copilot_auth import (
        GitHubCopilotAuthManager,
        GitHubCopilotAuthError,
    )
    
    print(f"Authenticating with {args.provider}...")
    
    try:
        with GitHubCopilotAuthManager() as auth_manager:
            auth_manager.login(open_browser=not args.no_browser)
        return 0
    except GitHubCopilotAuthError as e:
        print(f"❌ Authentication failed: {e}", file=sys.stderr)
        return 1


def cmd_auth_logout(args: argparse.Namespace) -> int:
    """Handle auth logout command."""
    from logai.auth.github_copilot_auth import GitHubCopilotAuthManager
    
    with GitHubCopilotAuthManager() as auth_manager:
        if auth_manager.logout():
            print(f"✓ Logged out from {args.provider}")
            return 0
        else:
            print(f"No credentials found for {args.provider}")
            return 0


def cmd_auth_status(args: argparse.Namespace) -> int:
    """Handle auth status command."""
    from logai.auth.github_copilot_auth import GitHubCopilotAuthManager
    
    print("Authentication Status")
    print("=" * 40)
    
    with GitHubCopilotAuthManager() as auth_manager:
        status = auth_manager.get_status()
        
        if status["authenticated"]:
            print(f"✓ GitHub Copilot: Authenticated")
            print(f"  Source: {status['source']}")
            print(f"  Token: {status['token_prefix']}")
        else:
            print(f"✗ GitHub Copilot: Not authenticated")
            print(f"  Run 'logai auth login' to authenticate")
        
        print(f"\nAuth file: {status['auth_file']}")
    
    return 0


def cmd_auth_list(args: argparse.Namespace) -> int:
    """Handle auth list command."""
    from logai.auth.github_copilot_auth import GitHubCopilotAuthManager
    from logai.providers.llm.github_copilot_provider import GITHUB_COPILOT_MODELS
    
    print("Available Providers")
    print("=" * 40)
    
    # Check GitHub Copilot status
    with GitHubCopilotAuthManager() as auth_manager:
        authenticated = auth_manager.is_authenticated()
        status_icon = "●" if authenticated else "○"
        print(f"\n{status_icon} github-copilot {'[authenticated]' if authenticated else ''}")
        print(f"  Models: {len(GITHUB_COPILOT_MODELS)} available")
        
        # Group by underlying provider
        providers = {}
        for model, info in GITHUB_COPILOT_MODELS.items():
            provider = info["provider"]
            if provider not in providers:
                providers[provider] = []
            providers[provider].append(model)
        
        for provider, models in sorted(providers.items()):
            print(f"  └ {provider}: {', '.join(sorted(models)[:3])}...")
    
    print("\n● LiteLLM Providers (configured via environment)")
    print("  └ anthropic, openai, ollama")
    
    return 0


def cmd_models(args: argparse.Namespace) -> int:
    """Handle models command."""
    from logai.providers.llm.github_copilot_provider import GITHUB_COPILOT_MODELS
    
    if args.provider == "github-copilot" or args.provider is None:
        print("GitHub Copilot Models")
        print("=" * 40)
        
        # Group by underlying provider
        providers = {}
        for model, info in GITHUB_COPILOT_MODELS.items():
            provider = info["provider"]
            if provider not in providers:
                providers[provider] = []
            providers[provider].append(model)
        
        for provider, models in sorted(providers.items()):
            print(f"\n{provider.title()}:")
            for model in sorted(models):
                print(f"  • github-copilot/{model}")
    
    return 0


def main() -> int:
    """Main CLI entry point."""
    parser = create_parser()
    args = parser.parse_args()
    
    # Route to appropriate command handler
    if args.command == "auth":
        if args.auth_command == "login":
            return cmd_auth_login(args)
        elif args.auth_command == "logout":
            return cmd_auth_logout(args)
        elif args.auth_command == "status":
            return cmd_auth_status(args)
        elif args.auth_command == "list":
            return cmd_auth_list(args)
        else:
            parser.parse_args(["auth", "--help"])
            return 1
    elif args.command == "models":
        return cmd_models(args)
    elif args.command == "run" or args.command is None:
        return cmd_run(args)
    else:
        parser.print_help()
        return 1


def cmd_run(args: argparse.Namespace) -> int:
    """Handle run command (main TUI startup)."""
    # ... existing main() logic from current cli.py ...
    # (This is the current main() function, moved here)
    pass


if __name__ == "__main__":
    sys.exit(main())
```

---

## 4. Data Flow Diagrams

### 4.1 OAuth Authentication Flow

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          OAuth Device Code Flow                                  │
└─────────────────────────────────────────────────────────────────────────────────┘

     User                        LogAI                         GitHub
       │                           │                              │
       │  $ logai auth login       │                              │
       │─────────────────────────▶│                              │
       │                           │                              │
       │                           │  POST /login/device/code     │
       │                           │  client_id, scope            │
       │                           │─────────────────────────────▶│
       │                           │                              │
       │                           │  device_code, user_code      │
       │                           │  verification_uri            │
       │                           │◀─────────────────────────────│
       │                           │                              │
       │  Display user_code        │                              │
       │  Open browser             │                              │
       │◀─────────────────────────│                              │
       │                           │                              │
       │  Enter code at github.com ────────────────────────────────▶│
       │  Authorize application    │                              │
       │                           │                              │
       │                           │  Poll: POST /login/oauth/    │
       │                           │  access_token                │
       │                           │─────────────────────────────▶│
       │                           │                              │
       │                           │  (authorization_pending)     │
       │                           │◀─────────────────────────────│
       │                           │                              │
       │                           │  ... user completes auth ... │
       │                           │                              │
       │                           │  Poll: POST /login/oauth/    │
       │                           │  access_token                │
       │                           │─────────────────────────────▶│
       │                           │                              │
       │                           │  access_token (gho_...)      │
       │                           │◀─────────────────────────────│
       │                           │                              │
       │                           │  Save to ~/.local/share/     │
       │                           │  logai/auth.json (600)       │
       │                           │─────────┐                    │
       │                           │         │                    │
       │                           │◀────────┘                    │
       │                           │                              │
       │  ✓ Authentication         │                              │
       │    successful!            │                              │
       │◀─────────────────────────│                              │
       │                           │                              │
```

### 4.2 Model Request Flow

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              Model Request Flow                                  │
└─────────────────────────────────────────────────────────────────────────────────┘

     User                LogAI TUI            GitHubCopilot         GitHub API
       │                     │                  Provider                 │
       │  "List log groups"  │                     │                     │
       │────────────────────▶│                     │                     │
       │                     │                     │                     │
       │                     │  Load token from    │                     │
       │                     │  auth.json or env   │                     │
       │                     │────────────────────▶│                     │
       │                     │                     │                     │
       │                     │  chat(messages,     │                     │
       │                     │       tools)        │                     │
       │                     │────────────────────▶│                     │
       │                     │                     │                     │
       │                     │                     │  POST /chat/        │
       │                     │                     │  completions        │
       │                     │                     │  Authorization:     │
       │                     │                     │  Bearer gho_...     │
       │                     │                     │────────────────────▶│
       │                     │                     │                     │
       │                     │                     │  {choices: [...],   │
       │                     │                     │   tool_calls: [...]}│
       │                     │                     │◀────────────────────│
       │                     │                     │                     │
       │                     │  LLMResponse        │                     │
       │                     │  (content,          │                     │
       │                     │   tool_calls)       │                     │
       │                     │◀────────────────────│                     │
       │                     │                     │                     │
       │                     │  Execute tool       │                     │
       │                     │  (list_log_groups)  │                     │
       │                     │─────────┐           │                     │
       │                     │         │           │                     │
       │                     │◀────────┘           │                     │
       │                     │                     │                     │
       │  Display results    │                     │                     │
       │◀────────────────────│                     │                     │
       │                     │                     │                     │
```

### 4.3 Token Validation Flow

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           Token Validation Flow                                  │
└─────────────────────────────────────────────────────────────────────────────────┘

                    ┌─────────────────────┐
                    │   get_token()       │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ Check env var       │
                    │ LOGAI_GITHUB_       │
                    │ COPILOT_TOKEN       │
                    └──────────┬──────────┘
                               │
                     ┌─────────┴─────────┐
                     │                   │
                   Found              Not Found
                     │                   │
                     ▼                   ▼
              ┌─────────────┐    ┌─────────────────┐
              │ Return env  │    │ Load auth.json  │
              │ token       │    │                 │
              └─────────────┘    └────────┬────────┘
                                          │
                               ┌──────────┴──────────┐
                               │                     │
                           File exists         File missing
                               │                     │
                               ▼                     ▼
                    ┌─────────────────┐    ┌─────────────────┐
                    │ Parse JSON      │    │ Return None     │
                    │ Get github-     │    │ (not auth'd)    │
                    │ copilot section │    └─────────────────┘
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │ Check expiration│
                    │ (expires_at)    │
                    └────────┬────────┘
                             │
                   ┌─────────┴─────────┐
                   │                   │
               Valid               Expired
                   │                   │
                   ▼                   ▼
            ┌─────────────┐    ┌─────────────────┐
            │ Return      │    │ Return None     │
            │ access_token│    │ (need re-auth)  │
            └─────────────┘    └─────────────────┘
```

---

## 5. File Structure

### 5.1 New Files to Create

```
src/logai/
├── auth/                               # NEW DIRECTORY
│   ├── __init__.py                     # Export auth classes
│   └── github_copilot_auth.py          # GitHub Copilot auth manager
│
├── providers/
│   └── llm/
│       ├── __init__.py                 # UPDATE: Add GitHubCopilotProvider
│       ├── base.py                     # No changes
│       ├── litellm_provider.py         # UPDATE: Add github-copilot case
│       └── github_copilot_provider.py  # NEW: GitHub Copilot provider
│
├── config/
│   └── settings.py                     # UPDATE: Add github-copilot settings
│
└── cli.py                              # UPDATE: Add auth subcommands

tests/
├── unit/
│   ├── test_github_copilot_auth.py     # NEW: Auth manager tests
│   └── test_github_copilot_provider.py # NEW: Provider tests
│
└── integration/
    └── test_github_copilot_e2e.py      # NEW: End-to-end tests (optional)
```

### 5.2 Configuration File Locations (XDG Compliant)

```
~/.config/logai/                        # Configuration
└── config.json                         # Main config (future feature)

~/.local/share/logai/                   # Data/credentials
└── auth.json                           # OAuth credentials (600 permissions)

~/.local/state/logai/                   # State (future feature)
└── model_history.json                  # Recent model usage

~/.cache/logai/                         # Cache
└── ...                                 # Existing cache
```

### 5.3 Auth File Format

**File:** `~/.local/share/logai/auth.json`  
**Permissions:** `600` (owner read/write only)

```json
{
  "github-copilot": {
    "type": "oauth",
    "access": "gho_xxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "refresh": "gho_xxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "expires": 0
  }
}
```

---

## 6. Security Considerations

### 6.1 Token Storage Security

| Aspect | OpenCode Approach | LogAI Approach | Improvement |
|--------|-------------------|----------------|-------------|
| File permissions | 644 (world-readable) | 600 (owner-only) | ✓ Better |
| Encryption | None (plaintext) | Optional keyring | ✓ Better |
| Environment fallback | Not supported | `LOGAI_GITHUB_COPILOT_TOKEN` | ✓ More flexible |
| Token masking in logs | Unknown | Always mask after 10 chars | ✓ Safer |

### 6.2 Security Implementation Details

```python
# 1. Secure file permissions (in auth manager)
os.chmod(auth_file, stat.S_IRUSR | stat.S_IWUSR)  # 600

# 2. Atomic file writes (prevent partial writes)
temp_file = auth_file.with_suffix(".tmp")
with open(temp_file, "w") as f:
    json.dump(data, f)
os.chmod(temp_file, 0o600)
temp_file.rename(auth_file)  # Atomic rename

# 3. Token masking in error messages
def _handle_http_error(self, response):
    error_message = response.text
    if "gho_" in error_message:
        error_message = "Authentication failed (token error)"
    # ...

# 4. Token masking for display
def _mask_token(self, token: str) -> str:
    if len(token) > 10:
        return f"{token[:10]}..."
    return "***"
```

### 6.3 Optional Keyring Integration (Future Enhancement)

For users who want additional security, support optional keyring storage:

```python
# Optional keyring support (if keyring library is installed)
try:
    import keyring
    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False

def _save_to_keyring(self, token: str) -> bool:
    """Save token to system keyring."""
    if not KEYRING_AVAILABLE:
        return False
    try:
        keyring.set_password("logai", "github-copilot", token)
        return True
    except Exception:
        return False

def _load_from_keyring(self) -> str | None:
    """Load token from system keyring."""
    if not KEYRING_AVAILABLE:
        return None
    try:
        return keyring.get_password("logai", "github-copilot")
    except Exception:
        return None
```

### 6.4 Security Checklist

- [ ] Auth file created with 600 permissions
- [ ] Atomic file writes to prevent corruption
- [ ] Token never logged in full (always masked)
- [ ] Error messages sanitized to remove token
- [ ] Environment variable takes precedence (for CI/CD)
- [ ] No hardcoded credentials in code
- [ ] Secure deletion on logout

---

## 7. API Integration Details

### 7.1 GitHub Copilot API Endpoint

**URL:** `https://api.githubcopilot.com/chat/completions`  
**Method:** `POST`  
**Authentication:** Bearer token

### 7.2 Request Headers

```http
POST /chat/completions HTTP/1.1
Host: api.githubcopilot.com
Authorization: Bearer gho_xxxxxxxxxxxxxxxxxxxxxxxxxxxx
Content-Type: application/json
Accept: application/json
```

### 7.3 Request Body Format

```json
{
  "model": "claude-sonnet-4.5",
  "messages": [
    {
      "role": "system",
      "content": "You are a helpful assistant."
    },
    {
      "role": "user",
      "content": "List my AWS log groups"
    }
  ],
  "temperature": 0.7,
  "max_tokens": 4096,
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "list_log_groups",
        "description": "List CloudWatch log groups",
        "parameters": {
          "type": "object",
          "properties": {},
          "required": []
        }
      }
    }
  ]
}
```

### 7.4 Response Format (OpenAI-Compatible)

```json
{
  "id": "chatcmpl-abc123",
  "object": "chat.completion",
  "created": 1707582200,
  "model": "claude-sonnet-4.5",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": null,
        "tool_calls": [
          {
            "id": "call_xyz789",
            "type": "function",
            "function": {
              "name": "list_log_groups",
              "arguments": "{}"
            }
          }
        ]
      },
      "finish_reason": "tool_calls"
    }
  ],
  "usage": {
    "prompt_tokens": 150,
    "completion_tokens": 25,
    "total_tokens": 175
  }
}
```

### 7.5 Error Response Format

```json
{
  "error": {
    "message": "Invalid authentication credentials",
    "type": "authentication_error",
    "code": "invalid_api_key"
  }
}
```

### 7.6 Error Handling Matrix

| HTTP Status | Error Type | LogAI Exception | Retry? |
|-------------|------------|-----------------|--------|
| 401 | Unauthorized | `AuthenticationError` | No (re-auth needed) |
| 429 | Rate Limited | `RateLimitError` | Yes (exponential backoff) |
| 400 | Bad Request | `InvalidRequestError` | No (fix request) |
| 500-599 | Server Error | `LLMProviderError` | Yes (with backoff) |
| Timeout | - | `LLMProviderError` | Yes (with backoff) |

---

## 8. Configuration Examples

### 8.1 Environment Variables (`.env`)

```bash
# === LLM Provider Selection ===
LOGAI_LLM_PROVIDER=github-copilot

# === GitHub Copilot Configuration ===
# Model to use (default: claude-sonnet-4.5)
LOGAI_GITHUB_COPILOT_MODEL=claude-sonnet-4.5

# Temperature (default: 0.7)
LOGAI_GITHUB_COPILOT_TEMPERATURE=0.7

# Optional: Direct token (for CI/CD, overrides auth.json)
# LOGAI_GITHUB_COPILOT_TOKEN=gho_xxxxxxxxxxxxxxxxxxxxxxxxxxxx

# === AWS Configuration (unchanged) ===
AWS_DEFAULT_REGION=us-east-1
AWS_PROFILE=my-profile
```

### 8.2 Settings Configuration

```python
# In settings.py, using pydantic-settings

class LogAISettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LOGAI_",
        env_file=".env",
        case_sensitive=False,
    )
    
    # Provider selection now includes github-copilot
    llm_provider: Literal["anthropic", "openai", "ollama", "github-copilot"] = "anthropic"
    
    # GitHub Copilot specific
    github_copilot_model: str = "claude-sonnet-4.5"
    github_copilot_temperature: float = 0.7
    github_copilot_max_tokens: int | None = None
```

### 8.3 CLI Usage Examples

```bash
# Authenticate with GitHub Copilot
$ logai auth login
Authenticating with github-copilot...

============================================================
GitHub Copilot Authentication
============================================================

1. Open: https://github.com/login/device
2. Enter code: ABCD-1234

Waiting for authentication...

✓ Authentication successful!

# Check authentication status
$ logai auth status
Authentication Status
========================================
✓ GitHub Copilot: Authenticated
  Source: file
  Token: gho_xxxxxx...

Auth file: /Users/user/.local/share/logai/auth.json

# List available models
$ logai models github-copilot
GitHub Copilot Models
========================================

Anthropic:
  • github-copilot/claude-haiku-4.5
  • github-copilot/claude-opus-4.5
  • github-copilot/claude-opus-4.6
  • github-copilot/claude-opus-41
  • github-copilot/claude-sonnet-4
  • github-copilot/claude-sonnet-4.5

Google:
  • github-copilot/gemini-2.5-pro
  • github-copilot/gemini-3-flash-preview
  • github-copilot/gemini-3-pro-preview

Openai:
  • github-copilot/gpt-4.1
  • github-copilot/gpt-4o
  • github-copilot/gpt-5
  • github-copilot/gpt-5-mini
  ...

# Start LogAI with GitHub Copilot
$ LOGAI_LLM_PROVIDER=github-copilot logai
LogAI v0.1.0
✓ LLM Provider: github-copilot
✓ LLM Model: github-copilot/claude-sonnet-4.5
✓ AWS Region: us-east-1
...
```

---

## 9. Compatibility Considerations

### 9.1 Provider Selection Logic

```python
# In litellm_provider.py (or new provider_factory.py)

def create_provider(settings: LogAISettings) -> BaseLLMProvider:
    """Create appropriate LLM provider based on settings."""
    if settings.llm_provider == "github-copilot":
        from logai.providers.llm.github_copilot_provider import GitHubCopilotProvider
        return GitHubCopilotProvider.from_settings(settings)
    else:
        # Existing providers via LiteLLM
        from logai.providers.llm.litellm_provider import LiteLLMProvider
        return LiteLLMProvider.from_settings(settings)
```

### 9.2 Fallback Behavior

If GitHub Copilot authentication fails:

```python
def create_provider_with_fallback(settings: LogAISettings) -> BaseLLMProvider:
    """Create provider with fallback on auth failure."""
    if settings.llm_provider == "github-copilot":
        try:
            provider = GitHubCopilotProvider.from_settings(settings)
            # Verify authentication
            if not provider._auth_manager.is_authenticated():
                print("⚠ Not authenticated with GitHub Copilot")
                print("  Run 'logai auth login' or set LOGAI_GITHUB_COPILOT_TOKEN")
                raise AuthenticationError(
                    "Not authenticated",
                    provider="github-copilot",
                    error_code="not_authenticated",
                )
            return provider
        except AuthenticationError:
            raise  # Don't fallback, require explicit auth
    
    return LiteLLMProvider.from_settings(settings)
```

### 9.3 Model String Format Compatibility

```python
# Support both formats:
# - "github-copilot/claude-sonnet-4.5" (full format)
# - "claude-sonnet-4.5" (model only, when provider is github-copilot)

def normalize_model_name(model: str, provider: str) -> str:
    """Normalize model name based on provider."""
    if provider == "github-copilot":
        # Strip provider prefix if present
        if model.startswith("github-copilot/"):
            return model[len("github-copilot/"):]
        return model
    return model
```

---

## 10. Testing Strategy

### 10.1 Unit Test Requirements

**File:** `tests/unit/test_github_copilot_auth.py`

```python
"""Tests for GitHub Copilot authentication manager."""

import json
import os
import stat
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from logai.auth.github_copilot_auth import (
    AuthenticationDeniedError,
    AuthenticationTimeoutError,
    DeviceCodeResponse,
    GitHubCopilotAuthError,
    GitHubCopilotAuthManager,
    OAuthCredentials,
)


class TestOAuthCredentials:
    """Tests for OAuthCredentials dataclass."""
    
    def test_is_valid_with_token(self):
        """Valid token should return True."""
        creds = OAuthCredentials(access_token="gho_test123")
        assert creds.is_valid() is True
    
    def test_is_valid_without_token(self):
        """Empty token should return False."""
        creds = OAuthCredentials(access_token="")
        assert creds.is_valid() is False
    
    def test_is_valid_expired(self):
        """Expired token should return False."""
        creds = OAuthCredentials(
            access_token="gho_test123",
            expires_at=1,  # Expired (1970)
        )
        assert creds.is_valid() is False
    
    def test_to_dict(self):
        """Should serialize to expected format."""
        creds = OAuthCredentials(
            access_token="gho_test123",
            refresh_token="gho_refresh456",
            expires_at=0,
        )
        assert creds.to_dict() == {
            "type": "oauth",
            "access": "gho_test123",
            "refresh": "gho_refresh456",
            "expires": 0,
        }
    
    def test_from_dict(self):
        """Should deserialize from expected format."""
        data = {
            "type": "oauth",
            "access": "gho_test123",
            "refresh": "gho_refresh456",
            "expires": 0,
        }
        creds = OAuthCredentials.from_dict(data)
        assert creds.access_token == "gho_test123"
        assert creds.refresh_token == "gho_refresh456"


class TestGitHubCopilotAuthManager:
    """Tests for GitHubCopilotAuthManager."""
    
    @pytest.fixture
    def temp_auth_file(self, tmp_path: Path) -> Path:
        """Create temp auth file path."""
        return tmp_path / "auth.json"
    
    @pytest.fixture
    def auth_manager(self, temp_auth_file: Path) -> GitHubCopilotAuthManager:
        """Create auth manager with temp file."""
        return GitHubCopilotAuthManager(auth_file_path=temp_auth_file)
    
    def test_is_authenticated_false_when_no_file(self, auth_manager):
        """Should return False when no auth file."""
        assert auth_manager.is_authenticated() is False
    
    def test_is_authenticated_true_with_valid_token(
        self, auth_manager, temp_auth_file
    ):
        """Should return True with valid token in file."""
        auth_data = {
            "github-copilot": {
                "type": "oauth",
                "access": "gho_test123",
                "refresh": "",
                "expires": 0,
            }
        }
        temp_auth_file.parent.mkdir(parents=True, exist_ok=True)
        temp_auth_file.write_text(json.dumps(auth_data))
        
        assert auth_manager.is_authenticated() is True
    
    def test_get_token_from_env_var(self, auth_manager, monkeypatch):
        """Environment variable should take precedence."""
        monkeypatch.setenv("LOGAI_GITHUB_COPILOT_TOKEN", "gho_env_token")
        assert auth_manager.get_token() == "gho_env_token"
    
    def test_save_credentials_creates_file_with_600_permissions(
        self, auth_manager, temp_auth_file
    ):
        """Should create file with 600 permissions."""
        creds = OAuthCredentials(access_token="gho_test123")
        auth_manager._save_credentials(creds)
        
        assert temp_auth_file.exists()
        mode = temp_auth_file.stat().st_mode
        assert mode & 0o777 == 0o600
    
    def test_logout_removes_credentials(
        self, auth_manager, temp_auth_file
    ):
        """Should remove credentials on logout."""
        # Create auth file
        auth_data = {"github-copilot": {"type": "oauth", "access": "gho_test123"}}
        temp_auth_file.parent.mkdir(parents=True, exist_ok=True)
        temp_auth_file.write_text(json.dumps(auth_data))
        
        result = auth_manager.logout()
        
        assert result is True
        assert not temp_auth_file.exists()
    
    def test_get_status(self, auth_manager, temp_auth_file):
        """Should return correct status dict."""
        status = auth_manager.get_status()
        
        assert "authenticated" in status
        assert "auth_file" in status
        assert status["authenticated"] is False
    
    @patch("httpx.Client.post")
    def test_request_device_code(self, mock_post, auth_manager):
        """Should request device code correctly."""
        mock_post.return_value = Mock(
            status_code=200,
            json=Mock(return_value={
                "device_code": "dc_123",
                "user_code": "ABCD-1234",
                "verification_uri": "https://github.com/login/device",
                "expires_in": 900,
                "interval": 5,
            }),
        )
        
        response = auth_manager._request_device_code()
        
        assert response.user_code == "ABCD-1234"
        assert response.verification_uri == "https://github.com/login/device"
```

**File:** `tests/unit/test_github_copilot_provider.py`

```python
"""Tests for GitHub Copilot provider."""

from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from logai.providers.llm.base import (
    AuthenticationError,
    LLMResponse,
    RateLimitError,
)
from logai.providers.llm.github_copilot_provider import (
    DEFAULT_MODEL,
    GITHUB_COPILOT_MODELS,
    GitHubCopilotProvider,
)


class TestGitHubCopilotProvider:
    """Tests for GitHubCopilotProvider."""
    
    @pytest.fixture
    def mock_auth_manager(self):
        """Create mock auth manager."""
        manager = Mock()
        manager.get_token.return_value = "gho_test_token_123"
        manager.is_authenticated.return_value = True
        return manager
    
    @pytest.fixture
    def provider(self, mock_auth_manager):
        """Create provider with mock auth."""
        return GitHubCopilotProvider(
            model="claude-sonnet-4.5",
            auth_manager=mock_auth_manager,
        )
    
    def test_initialization_default_model(self, mock_auth_manager):
        """Should use default model."""
        provider = GitHubCopilotProvider(auth_manager=mock_auth_manager)
        assert provider.model == DEFAULT_MODEL
    
    def test_initialization_strips_provider_prefix(self, mock_auth_manager):
        """Should strip github-copilot/ prefix."""
        provider = GitHubCopilotProvider(
            model="github-copilot/claude-sonnet-4.5",
            auth_manager=mock_auth_manager,
        )
        assert provider.model == "claude-sonnet-4.5"
    
    def test_full_model_name(self, provider):
        """Should return full model name with prefix."""
        assert provider.full_model_name == "github-copilot/claude-sonnet-4.5"
    
    def test_get_available_models(self):
        """Should return all available models."""
        models = GitHubCopilotProvider.get_available_models()
        assert "claude-sonnet-4.5" in models
        assert "gpt-5" in models
        assert len(models) > 20
    
    def test_supports_tools(self, provider):
        """Should check tool support correctly."""
        assert provider._supports_tools() is True
    
    @pytest.mark.asyncio
    async def test_chat_not_authenticated(self, mock_auth_manager):
        """Should raise error when not authenticated."""
        mock_auth_manager.get_token.return_value = None
        provider = GitHubCopilotProvider(auth_manager=mock_auth_manager)
        
        with pytest.raises(AuthenticationError):
            await provider.chat([{"role": "user", "content": "Hello"}])
    
    @pytest.mark.asyncio
    async def test_chat_success(self, provider):
        """Should return LLMResponse on success."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{
                "message": {"role": "assistant", "content": "Hello!"},
                "finish_reason": "stop",
            }],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
        }
        
        with patch.object(
            provider, "_get_http_client",
            return_value=AsyncMock(post=AsyncMock(return_value=mock_response)),
        ):
            response = await provider.chat([{"role": "user", "content": "Hi"}])
        
        assert isinstance(response, LLMResponse)
        assert response.content == "Hello!"
        assert response.usage["total_tokens"] == 15
    
    @pytest.mark.asyncio
    async def test_chat_rate_limit_error(self, provider):
        """Should raise RateLimitError on 429."""
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.text = "Rate limit exceeded"
        mock_response.json.return_value = {"error": {"message": "Rate limit"}}
        
        with patch.object(
            provider, "_get_http_client",
            return_value=AsyncMock(post=AsyncMock(return_value=mock_response)),
        ):
            with pytest.raises(RateLimitError):
                await provider.chat([{"role": "user", "content": "Hi"}])
    
    def test_handle_http_error_masks_token(self, provider):
        """Should mask token in error messages."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = "Invalid token gho_secret_token_12345"
        mock_response.json.side_effect = Exception("No JSON")
        
        with pytest.raises(AuthenticationError) as exc_info:
            provider._handle_http_error(mock_response)
        
        # Token should be masked in error
        assert "gho_secret_token" not in str(exc_info.value)
```

### 10.2 Integration Test Requirements

```python
"""Integration tests for GitHub Copilot (requires auth)."""

import os

import pytest

from logai.auth.github_copilot_auth import GitHubCopilotAuthManager
from logai.providers.llm.github_copilot_provider import GitHubCopilotProvider


@pytest.fixture
def authenticated_provider():
    """Create authenticated provider (skips if no auth)."""
    auth_manager = GitHubCopilotAuthManager()
    if not auth_manager.is_authenticated():
        pytest.skip("GitHub Copilot authentication required")
    return GitHubCopilotProvider(auth_manager=auth_manager)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_api_request(authenticated_provider):
    """Test real API request."""
    response = await authenticated_provider.chat([
        {"role": "user", "content": "Say 'test' and nothing else."}
    ])
    
    assert response.content is not None
    assert "test" in response.content.lower()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_api_with_tools(authenticated_provider):
    """Test real API request with tools."""
    tools = [{
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get weather for a city",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City name"}
                },
                "required": ["city"],
            },
        },
    }]
    
    response = await authenticated_provider.chat(
        messages=[{"role": "user", "content": "What's the weather in Tokyo?"}],
        tools=tools,
    )
    
    # Model should either respond or call tool
    assert response.content is not None or response.has_tool_calls()
```

### 10.3 Test Coverage Goals

| Component | Target Coverage | Priority |
|-----------|-----------------|----------|
| `github_copilot_auth.py` | 90%+ | High |
| `github_copilot_provider.py` | 85%+ | High |
| Settings changes | 80%+ | Medium |
| CLI commands | 70%+ | Medium |

---

## 11. Implementation Phases

### Phase 1: Foundation (Day 1-2)
**Complexity: Simple**

**Tasks:**
1. Create `src/logai/auth/` directory structure
2. Create `src/logai/auth/__init__.py`
3. Create `src/logai/auth/github_copilot_auth.py` with:
   - `OAuthCredentials` dataclass
   - `DeviceCodeResponse` dataclass
   - `GitHubCopilotAuthManager` class (skeleton)

**Files to Create:**
- `src/logai/auth/__init__.py`
- `src/logai/auth/github_copilot_auth.py`

**Success Criteria:**
- [ ] Module imports without errors
- [ ] `OAuthCredentials` can serialize/deserialize
- [ ] Auth file path follows XDG spec

**Dependencies:** None

---

### Phase 2: Authentication Implementation (Day 2-4)
**Complexity: Moderate**

**Tasks:**
1. Implement `_request_device_code()` method
2. Implement `_poll_for_token()` method
3. Implement `login()` method (full OAuth flow)
4. Implement `logout()` method
5. Implement credential storage with 600 permissions
6. Add unit tests for auth module

**Files to Modify:**
- `src/logai/auth/github_copilot_auth.py` (complete implementation)

**Files to Create:**
- `tests/unit/test_github_copilot_auth.py`

**Success Criteria:**
- [ ] `login()` successfully completes OAuth flow
- [ ] Credentials stored with 600 permissions
- [ ] `logout()` removes credentials
- [ ] Environment variable override works
- [ ] 80%+ test coverage for auth module

**Dependencies:** Phase 1

---

### Phase 3: Provider Implementation (Day 4-6)
**Complexity: Simple**

**Tasks:**
1. Create `GitHubCopilotProvider` class
2. Implement `chat()` method
3. Implement `stream_chat()` method
4. Implement error handling
5. Add model list and validation
6. Add unit tests for provider

**Files to Create:**
- `src/logai/providers/llm/github_copilot_provider.py`
- `tests/unit/test_github_copilot_provider.py`

**Files to Modify:**
- `src/logai/providers/llm/__init__.py` (add export)

**Success Criteria:**
- [ ] Provider can make authenticated requests
- [ ] Response parsing works correctly
- [ ] Tool calls are handled
- [ ] Errors map to correct exception types
- [ ] Token never appears in error messages

**Dependencies:** Phase 2

---

### Phase 4: Settings Integration (Day 6-7)
**Complexity: Simple**

**Tasks:**
1. Add `github-copilot` to `llm_provider` Literal type
2. Add `github_copilot_model` setting
3. Add `github_copilot_temperature` setting
4. Add `github_copilot_max_tokens` setting
5. Update `validate_required_credentials()` method
6. Update `current_llm_model` property
7. Update `.env.example`

**Files to Modify:**
- `src/logai/config/settings.py`
- `.env.example`

**Files to Create/Modify:**
- `tests/unit/test_settings.py` (add tests)

**Success Criteria:**
- [ ] `LOGAI_LLM_PROVIDER=github-copilot` works
- [ ] Model/temperature/max_tokens settings work
- [ ] Validation passes for github-copilot provider

**Dependencies:** Phase 3

---

### Phase 5: CLI Commands (Day 7-9)
**Complexity: Simple**

**Tasks:**
1. Refactor CLI to use subparsers
2. Add `auth` subcommand group
3. Implement `logai auth login`
4. Implement `logai auth logout`
5. Implement `logai auth status`
6. Implement `logai auth list`
7. Implement `logai models` command
8. Add CLI tests

**Files to Modify:**
- `src/logai/cli.py`

**Files to Create/Modify:**
- `tests/unit/test_cli.py` (add auth tests)

**Success Criteria:**
- [ ] `logai auth login` initiates OAuth flow
- [ ] `logai auth logout` removes credentials
- [ ] `logai auth status` shows auth state
- [ ] `logai models github-copilot` lists models
- [ ] Backward compatibility maintained

**Dependencies:** Phase 4

---

### Phase 6: Integration (Day 9-10)
**Complexity: Simple**

**Tasks:**
1. Update `LiteLLMProvider.from_settings()` or create factory
2. Update `cli.py` main entry point to use GitHub Copilot
3. Test end-to-end flow with TUI
4. Update README.md with GitHub Copilot instructions

**Files to Modify:**
- `src/logai/providers/llm/litellm_provider.py` (add github-copilot case)
- `src/logai/cli.py` (provider selection)
- `README.md` (documentation)

**Success Criteria:**
- [ ] `LOGAI_LLM_PROVIDER=github-copilot logai` starts TUI
- [ ] Queries work with GitHub Copilot models
- [ ] Tool calling works correctly

**Dependencies:** Phase 5

---

### Phase 7: Testing & Polish (Day 10-12)
**Complexity: Moderate**

**Tasks:**
1. Write integration tests (optional, requires real auth)
2. Test all error scenarios
3. Add debug logging
4. Review and improve error messages
5. Final code review and cleanup
6. Update all documentation

**Files to Create:**
- `tests/integration/test_github_copilot_e2e.py` (optional)

**Success Criteria:**
- [ ] 85%+ overall test coverage
- [ ] All error scenarios handled gracefully
- [ ] Documentation complete
- [ ] Code passes linting

**Dependencies:** Phase 6

---

### Phase Summary

| Phase | Duration | Complexity | Dependencies |
|-------|----------|------------|--------------|
| 1. Foundation | 1-2 days | Simple | None |
| 2. Auth Implementation | 2-3 days | Moderate | Phase 1 |
| 3. Provider Implementation | 2-3 days | Simple | Phase 2 |
| 4. Settings Integration | 1-2 days | Simple | Phase 3 |
| 5. CLI Commands | 2-3 days | Simple | Phase 4 |
| 6. Integration | 1-2 days | Simple | Phase 5 |
| 7. Testing & Polish | 2-3 days | Moderate | Phase 6 |
| **Total** | **~12 days** | | |

---

## 12. Migration and Rollout

### 12.1 Adoption Path for Existing Users

1. **No Breaking Changes**: Existing users continue to use Anthropic/OpenAI/Ollama without changes
2. **Opt-In**: Users must explicitly:
   - Run `logai auth login` to authenticate
   - Set `LOGAI_LLM_PROVIDER=github-copilot` to switch providers
3. **Documentation**: Clear migration guide in README

### 12.2 Backward Compatibility

| Aspect | Compatibility |
|--------|--------------|
| Existing env vars | ✓ Still work |
| Existing CLI args | ✓ Still work |
| Config file format | ✓ No changes required |
| Provider API | ✓ Same `BaseLLMProvider` interface |

### 12.3 Documentation Updates Needed

1. **README.md**: Add GitHub Copilot section
2. **CHANGELOG.md**: Document new feature
3. **.env.example**: Add GitHub Copilot examples
4. **CLI help text**: Updated automatically via argparse

---

## 13. Appendices

### Appendix A: Full Model List

```python
GITHUB_COPILOT_MODELS = {
    # Claude models (Anthropic)
    "claude-haiku-4.5": {"provider": "anthropic", "supports_tools": True},
    "claude-sonnet-4": {"provider": "anthropic", "supports_tools": True},
    "claude-sonnet-4.5": {"provider": "anthropic", "supports_tools": True},
    "claude-opus-4.5": {"provider": "anthropic", "supports_tools": True},
    "claude-opus-4.6": {"provider": "anthropic", "supports_tools": True},
    "claude-opus-41": {"provider": "anthropic", "supports_tools": True},
    
    # OpenAI models
    "gpt-4.1": {"provider": "openai", "supports_tools": True},
    "gpt-4o": {"provider": "openai", "supports_tools": True},
    "gpt-5": {"provider": "openai", "supports_tools": True},
    "gpt-5-mini": {"provider": "openai", "supports_tools": True},
    "gpt-5.1": {"provider": "openai", "supports_tools": True},
    "gpt-5.1-codex": {"provider": "openai", "supports_tools": True},
    "gpt-5.1-codex-max": {"provider": "openai", "supports_tools": True},
    "gpt-5.1-codex-mini": {"provider": "openai", "supports_tools": True},
    "gpt-5.2": {"provider": "openai", "supports_tools": True},
    "gpt-5.2-codex": {"provider": "openai", "supports_tools": True},
    
    # Google models
    "gemini-2.5-pro": {"provider": "google", "supports_tools": True},
    "gemini-3-flash-preview": {"provider": "google", "supports_tools": True},
    "gemini-3-pro-preview": {"provider": "google", "supports_tools": True},
    
    # X.AI models
    "grok-code-fast-1": {"provider": "xai", "supports_tools": True},
}
```

### Appendix B: Error Code Reference

| Error Code | HTTP Status | Description | User Action |
|------------|-------------|-------------|-------------|
| `not_authenticated` | - | No token found | Run `logai auth login` |
| `unauthorized` | 401 | Token invalid/expired | Re-authenticate |
| `rate_limit` | 429 | Too many requests | Wait and retry |
| `bad_request` | 400 | Invalid request format | Check parameters |
| `http_5xx` | 5xx | Server error | Retry later |
| `timeout` | - | Request timed out | Check network |
| `network_error` | - | Connection failed | Check network |

### Appendix C: XDG Base Directory Reference

| Variable | Default | LogAI Usage |
|----------|---------|-------------|
| `XDG_CONFIG_HOME` | `~/.config` | Future config files |
| `XDG_DATA_HOME` | `~/.local/share` | `auth.json` |
| `XDG_STATE_HOME` | `~/.local/state` | Future model history |
| `XDG_CACHE_HOME` | `~/.cache` | Existing cache |

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-02-11 | Sally | Initial architecture document |

---

**End of Architecture Document**
