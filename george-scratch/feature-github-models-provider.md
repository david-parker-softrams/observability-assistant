# Feature Request: GitHub Models as LLM Provider

**Date:** February 11, 2026  
**Requested by:** User  
**Priority:** Medium  
**Status:** Ready for Implementation

---

## Overview

Add GitHub Models as an LLM provider option in LogAI, allowing users to leverage their GitHub credentials to access various AI models (GPT-4, Claude, Llama, etc.) through GitHub's free API tier.

## Motivation

GitHub Models provides free access to various AI models using GitHub credentials. This is beneficial for users who:

- Already have a GitHub account (likely all developers using LogAI)
- Want free/low-cost access to powerful AI models
- Prefer to consolidate their tool subscriptions under GitHub
- Have GitHub Copilot Pro/Business/Enterprise (higher rate limits)
- Want to experiment without separate OpenAI/Anthropic API keys

## What is GitHub Models?

GitHub Models is GitHub's AI model marketplace that provides:
- **Free API access** to multiple AI models
- **Authentication** via GitHub Personal Access Token
- **Multiple models**: GPT-4, Claude, Llama, Phi, Mistral, and more
- **Azure AI Inference SDK** compatibility
- **Rate limits** based on Copilot subscription tier

## Current Behavior

LogAI currently supports:
1. Anthropic Claude (via API key)
2. OpenAI GPT (via API key)  
3. Ollama (local models)

## Proposed Behavior

Add GitHub Models as a fourth provider option:

```bash
# Configure via environment variables
export LOGAI_LLM_PROVIDER=github
export LOGAI_GITHUB_TOKEN=ghp_xxxxxxxxxxxx
export LOGAI_GITHUB_MODEL=gpt-4o  # or claude-3-5-sonnet, etc.

# Run LogAI
logai --aws-profile myprofile
```

Or via command-line:
```bash
logai --llm-provider github --github-token ghp_xxx --github-model gpt-4o
```

## Technical Requirements

### 1. GitHub Token Authentication

GitHub Models requires a Personal Access Token (PAT) with `models:read` permission:

```python
# User creates token at: https://github.com/settings/tokens
# Needs scope: models:read
GITHUB_TOKEN = "ghp_xxxxxxxxxxxx"
```

### 2. API Endpoint

GitHub Models uses Azure AI Inference-compatible endpoints:

```python
BASE_URL = "https://models.inference.ai.azure.com"
# LiteLLM format: "azure_ai/<model-name>"
```

### 3. Available Models

GitHub Models provides access to:

**GPT Models (OpenAI):**
- `gpt-4o`
- `gpt-4o-mini`
- `gpt-4.1`
- `gpt-5-mini`

**Claude Models (Anthropic):**
- `claude-3-5-sonnet`
- `claude-3-5-haiku`

**Open Source Models:**
- `meta-llama-3.1-405b-instruct`
- `mistral-large-2407`
- `phi-4`
- `cohere-command-r-plus`

See full list: https://github.com/marketplace/models

### 4. LiteLLM Integration

LiteLLM already supports Azure AI Inference endpoints. We need to:

1. **Use the `azure_ai/` prefix** for GitHub Models:
   ```python
   model = "azure_ai/gpt-4o"
   base_url = "https://models.inference.ai.azure.com"
   api_key = github_token
   ```

2. **Set custom headers** for GitHub authentication:
   ```python
   headers = {
       "Authorization": f"Bearer {github_token}"
   }
   ```

### 5. Rate Limits

Rate limits vary by Copilot subscription tier:

| Tier | Requests/min | Requests/day | Tokens/request |
|------|-------------|--------------|----------------|
| **Copilot Free** | 15 (low), 10 (high) | 150 (low), 50 (high) | 8K in, 4K out |
| **Copilot Pro** | 15 (low), 10 (high) | 150 (low), 50 (high) | 8K in, 4K out |
| **Copilot Business** | 15 (low), 10 (high) | 300 (low), 100 (high) | 8K in, 4K out |
| **Copilot Enterprise** | 20 (low), 15 (high) | 450 (low), 150 (high) | 8K in, 8K out |

**Note:** These are free tier limits. Paid usage has higher limits.

## Implementation Details

### Configuration Changes

**File: `src/logai/config/settings.py`**

Add new settings:

```python
class Settings(BaseSettings):
    # ... existing settings ...
    
    # GitHub Models settings
    github_token: Optional[str] = Field(default=None, alias="LOGAI_GITHUB_TOKEN")
    github_model: str = Field(default="gpt-4o", alias="LOGAI_GITHUB_MODEL")
    
    @property
    def current_llm_model(self) -> str:
        """Get the current LLM model being used."""
        if self.llm_provider == "github":
            return self.github_model
        # ... existing logic for other providers ...
```

### LLM Provider Changes

**File: `src/logai/providers/llm/litellm_provider.py`**

Add GitHub Models support:

```python
class LiteLLMProvider(BaseLLMProvider):
    def __init__(
        self,
        provider: str,
        model: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        github_token: Optional[str] = None,  # NEW
    ):
        self.provider = provider
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.github_token = github_token  # NEW
        
    @classmethod
    def from_settings(cls, settings: Settings) -> "LiteLLMProvider":
        """Create provider from settings."""
        if settings.llm_provider == "github":
            return cls(
                provider="github",
                model=settings.github_model,
                github_token=settings.github_token,
                base_url="https://models.inference.ai.azure.com",
            )
        # ... existing logic for other providers ...
    
    def _get_model_name(self) -> str:
        """Get the full model name for LiteLLM."""
        if self.provider == "github":
            return f"azure_ai/{self.model}"
        # ... existing logic for other providers ...
    
    def _get_api_params(self) -> Dict[str, Any]:
        """Get API parameters for the provider."""
        if self.provider == "github":
            return {
                "api_key": self.github_token,
                "api_base": self.base_url,
                "extra_headers": {
                    "Authorization": f"Bearer {self.github_token}"
                }
            }
        # ... existing logic for other providers ...
```

### CLI Changes

**File: `src/logai/cli.py`**

Add optional CLI arguments:

```python
parser.add_argument(
    "--llm-provider",
    type=str,
    choices=["anthropic", "openai", "ollama", "github"],
    help="LLM provider to use (overrides LOGAI_LLM_PROVIDER)",
    default=None,
)

parser.add_argument(
    "--github-token",
    type=str,
    help="GitHub Personal Access Token for GitHub Models (overrides LOGAI_GITHUB_TOKEN)",
    default=None,
    metavar="TOKEN",
)

parser.add_argument(
    "--github-model",
    type=str,
    help="GitHub Models model name (e.g., gpt-4o, claude-3-5-sonnet)",
    default=None,
    metavar="MODEL",
)
```

Override settings from CLI args:

```python
# Override LLM settings from CLI arguments if provided
if args.llm_provider is not None:
    settings.llm_provider = args.llm_provider
if args.github_token is not None:
    settings.github_token = args.github_token
if args.github_model is not None:
    settings.github_model = args.github_model
```

### Validation

Add validation for GitHub provider:

```python
def validate_required_credentials(self) -> None:
    """Validate that required credentials are present."""
    if self.llm_provider == "github":
        if not self.github_token:
            raise ValueError(
                "GitHub Models requires LOGAI_GITHUB_TOKEN. "
                "Create a token at https://github.com/settings/tokens "
                "with 'models:read' permission."
            )
    # ... existing validation for other providers ...
```

## Usage Examples

### Example 1: Environment Variables

```bash
# Set up GitHub Models
export LOGAI_LLM_PROVIDER=github
export LOGAI_GITHUB_TOKEN=ghp_xxxxxxxxxxxx
export LOGAI_GITHUB_MODEL=gpt-4o

# Run LogAI
logai
```

### Example 2: Command-Line Arguments

```bash
logai --llm-provider github \
      --github-token ghp_xxxxxxxxxxxx \
      --github-model gpt-4o
```

### Example 3: Mix of Environment and CLI

```bash
# Token in environment (more secure)
export LOGAI_GITHUB_TOKEN=ghp_xxxxxxxxxxxx

# Model and AWS profile via CLI
logai --llm-provider github \
      --github-model claude-3-5-sonnet \
      --aws-profile prod
```

### Example 4: Switch Models Easily

```bash
# Try GPT-4o
logai --llm-provider github --github-model gpt-4o

# Try Claude
logai --llm-provider github --github-model claude-3-5-sonnet

# Try Llama
logai --llm-provider github --github-model meta-llama-3.1-405b-instruct
```

## Documentation Updates

### README.md

Add GitHub Models section:

```markdown
### GitHub Models

LogAI supports GitHub Models, which provides free access to various AI models using your GitHub credentials.

**Setup:**

1. Create a GitHub Personal Access Token:
   - Go to https://github.com/settings/tokens
   - Click "Generate new token (classic)"
   - Select the `models:read` scope
   - Copy the token (starts with `ghp_`)

2. Configure LogAI:
   ```bash
   export LOGAI_LLM_PROVIDER=github
   export LOGAI_GITHUB_TOKEN=ghp_xxxxxxxxxxxx
   export LOGAI_GITHUB_MODEL=gpt-4o  # or any supported model
   ```

3. Run LogAI:
   ```bash
   logai
   ```

**Supported Models:**
- GPT-4o, GPT-4o-mini, GPT-4.1, GPT-5-mini
- Claude 3.5 Sonnet, Claude 3.5 Haiku
- Meta Llama 3.1, Mistral Large, Phi-4, and more

See full list: https://github.com/marketplace/models

**Rate Limits:**
Free tier provides 10-20 requests/minute depending on your GitHub Copilot subscription.
For production use, opt in to paid GitHub Models usage.
```

### .env.example

Add GitHub Models configuration:

```bash
# GitHub Models Configuration (alternative to Anthropic/OpenAI)
# Create token at: https://github.com/settings/tokens (needs models:read scope)
# LOGAI_LLM_PROVIDER=github
# LOGAI_GITHUB_TOKEN=ghp_xxxxxxxxxxxx
# LOGAI_GITHUB_MODEL=gpt-4o  # or claude-3-5-sonnet, etc.
```

### Help Text

Update CLI help:

```python
Environment Variables:
  LOGAI_LLM_PROVIDER              # LLM provider: anthropic, openai, ollama, or github
  LOGAI_GITHUB_TOKEN              # GitHub PAT for GitHub Models (provider=github)
  LOGAI_GITHUB_MODEL              # Model name for GitHub Models (default: gpt-4o)
  ...

Examples:
  logai --llm-provider github --github-model gpt-4o
```

## Testing Strategy

### Unit Tests

**File: `tests/unit/test_github_models_provider.py`**

```python
def test_github_models_provider_initialization():
    """Test GitHub Models provider can be initialized."""
    provider = LiteLLMProvider(
        provider="github",
        model="gpt-4o",
        github_token="ghp_test_token",
        base_url="https://models.inference.ai.azure.com",
    )
    assert provider.provider == "github"
    assert provider.model == "gpt-4o"
    assert provider._get_model_name() == "azure_ai/gpt-4o"

def test_github_models_from_settings():
    """Test creating provider from settings."""
    settings = Settings(
        llm_provider="github",
        github_token="ghp_test_token",
        github_model="claude-3-5-sonnet",
    )
    provider = LiteLLMProvider.from_settings(settings)
    assert provider.provider == "github"
    assert provider.model == "claude-3-5-sonnet"

def test_github_models_requires_token():
    """Test that GitHub provider requires token."""
    settings = Settings(
        llm_provider="github",
        github_token=None,
    )
    with pytest.raises(ValueError, match="GitHub Models requires LOGAI_GITHUB_TOKEN"):
        settings.validate_required_credentials()
```

### Integration Tests

Manual testing:

1. **Create GitHub Token**:
   ```bash
   # Go to https://github.com/settings/tokens
   # Create token with models:read scope
   export LOGAI_GITHUB_TOKEN=ghp_real_token
   ```

2. **Test with GPT-4o**:
   ```bash
   logai --llm-provider github --github-model gpt-4o
   # In TUI: "List all my log groups"
   ```

3. **Test with Claude**:
   ```bash
   logai --llm-provider github --github-model claude-3-5-sonnet
   # In TUI: "List all my log groups"
   ```

4. **Test Rate Limiting**:
   ```bash
   # Make rapid requests to verify rate limiting is handled
   ```

## Benefits

1. **No Additional API Keys**: Use existing GitHub credentials
2. **Free Tier**: Good for personal use and experimentation
3. **Multiple Models**: Access to GPT-4, Claude, Llama, and more
4. **Unified Billing**: For users with Copilot, everything under GitHub
5. **Easy Model Switching**: Try different models without multiple API accounts

## Trade-offs

**Pros:**
- Free tier with decent rate limits
- Access to multiple model providers through one token
- Great for developers already using GitHub
- Easy to get started (just need a GitHub account)

**Cons:**
- Rate limits are lower than direct OpenAI/Anthropic APIs
- Requires internet connection (can't run fully offline like Ollama)
- Another dependency on GitHub's infrastructure
- Token needs careful management (security risk if exposed)

## Success Criteria

1. ✅ User can configure GitHub Models via environment variables
2. ✅ User can configure GitHub Models via CLI arguments
3. ✅ LogAI can authenticate with GitHub using PAT
4. ✅ LogAI can make successful API calls to GitHub Models
5. ✅ Tool calling (CloudWatch functions) works with GitHub Models
6. ✅ Error messages are clear when token is missing or invalid
7. ✅ Documentation is complete and user-friendly
8. ✅ All tests pass
9. ✅ Code review approved

## Open Questions

1. **Should we support model auto-selection?**
   - Let GitHub Models pick the best model based on the query?
   - Or always require explicit model selection?

2. **Should we add model aliases?**
   - E.g., `--github-model gpt-4` maps to `gpt-4o`?
   - Makes it easier for users familiar with OpenAI naming?

3. **Should we add token validation on startup?**
   - Make a test API call to verify token is valid?
   - Or wait for first real request and handle error then?

4. **Should we cache the token securely?**
   - Add keychain/keyring support for token storage?
   - Or always require environment variable/CLI arg?

## References

- **GitHub Models Documentation**: https://docs.github.com/en/github-models
- **GitHub Models Marketplace**: https://github.com/marketplace/models
- **Creating GitHub PAT**: https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens
- **Azure AI Inference SDK**: https://learn.microsoft.com/en-us/azure/ai-studio/how-to/
- **LiteLLM Azure AI Support**: https://docs.litellm.ai/docs/providers/azure_ai

## Implementation Assignment

**Assigned to:** Jackie (software-engineer agent)  
**Estimated Effort:** Medium feature (2-4 hours)  
**Complexity:** Medium - requires LiteLLM provider addition and configuration updates

**Review by:** Billy (code-reviewer agent)  
**Testing by:** Raoul (qa-engineer agent)  
**Documentation by:** Tina (technical-writer agent)

---

**Status:** Ready for implementation after user approval
