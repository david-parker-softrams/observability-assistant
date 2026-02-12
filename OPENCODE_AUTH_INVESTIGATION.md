# OpenCode GitHub Copilot Authentication Investigation Report

## Executive Summary

OpenCode implements GitHub Copilot authentication using OAuth tokens stored locally in `~/.local/share/opencode/auth.json`. The system communicates with `https://api.githubcopilot.com/chat/completions` endpoint using Bearer token authentication.

## 1. Configuration Storage

### Primary Locations
- **Config**: `~/.config/opencode/config.json` - Contains model selections and agent configuration
- **Auth**: `~/.local/share/opencode/auth.json` - Stores OAuth credentials
- **State**: `~/.local/state/opencode/` - Stores model history and prompt history
- **Cache**: `~/.local/share/opencode/` - Stores sessions, messages, and tool outputs

### Auth File Structure
```json
{
  "github-copilot": {
    "type": "oauth",
    "access": "gho_XXXXXXXXXXXXXXXXXXXXXXXXXXX",
    "refresh": "gho_XXXXXXXXXXXXXXXXXXXXXXXXXXX",
    "expires": 0
  }
}
```

**Key Points:**
- `type`: "oauth" - Indicates OAuth-based authentication
- `access`: GitHub OAuth token (starts with `gho_`)
- `refresh`: Refresh token (same value as access in current setup)
- `expires`: 0 indicates no expiration set

## 2. Authentication Mechanism

### OAuth Flow
OpenCode uses GitHub's OAuth flow for authentication:

1. **Login Command**: `opencode auth login [url]`
2. **Provider**: GitHub Copilot (identified as "github-copilot")
3. **Token Type**: GitHub Personal Access Token (PAT) - OAuth tokens starting with `gho_` prefix

### Authentication Status Check
```bash
$ opencode auth list

Credentials ~/.local/share/opencode/auth.json
● GitHub Copilot [oauth]
└ 1 credentials

Environment
● Amazon Bedrock [AWS_ACCESS_KEY_ID]
● Amazon Bedrock [AWS_SECRET_ACCESS_KEY]
● Amazon Bedrock [AWS_REGION]
└ 3 environment variables
```

**Note**: OpenCode also supports environment-based authentication (e.g., AWS credentials for Bedrock)

## 3. API Endpoint

### Primary Endpoint
**URL**: `https://api.githubcopilot.com/chat/completions`

This is the standard GitHub Copilot chat completions endpoint that handles:
- Model inference requests
- Chat-based interactions
- Support for multiple models (see section 4)

### Authentication Header
```
Authorization: Bearer {access_token}
```

The access token from auth.json is passed as a Bearer token in the Authorization header.

## 4. Available Models

OpenCode supports the following `github-copilot/` provider models:

**Claude Models:**
- `github-copilot/claude-haiku-4.5` (small_model in config)
- `github-copilot/claude-opus-4.5`
- `github-copilot/claude-opus-4.6`
- `github-copilot/claude-sonnet-4` 
- `github-copilot/claude-sonnet-4.5` (default model)
- `github-copilot/claude-opus-41`

**OpenAI Models:**
- `github-copilot/gpt-4.1`
- `github-copilot/gpt-4o`
- `github-copilot/gpt-5`
- `github-copilot/gpt-5-mini`
- `github-copilot/gpt-5.1`
- `github-copilot/gpt-5.1-codex`
- `github-copilot/gpt-5.1-codex-max`
- `github-copilot/gpt-5.1-codex-mini`
- `github-copilot/gpt-5.2`
- `github-copilot/gpt-5.2-codex`

**Google Models:**
- `github-copilot/gemini-2.5-pro`
- `github-copilot/gemini-3-flash-preview`
- `github-copilot/gemini-3-pro-preview`

**Other:**
- `github-copilot/grok-code-fast-1`

## 5. Authentication File Locations

### macOS XDG Compliance
OpenCode follows XDG Base Directory specification on macOS:

```
$HOME/.config/opencode/        - Configuration files
$HOME/.local/share/opencode/   - Shared data (auth, sessions, snapshots)
$HOME/.local/state/opencode/   - State information (history, logs)
$HOME/.cache/opencode/         - Cache files
```

### Sub-directories
```
~/.local/share/opencode/
├── auth.json                  - OAuth credentials
├── storage/
│   ├── message/              - Chat message storage (JSONL)
│   ├── session/              - Session metadata
│   ├── session_diff/         - Session diff tracking
│   └── todo/                 - Todo items
├── snapshot/                 - Session snapshots
└── log/                       - Application logs
```

## 6. macOS Keychain Integration

**Finding**: No macOS Keychain entries found for OpenCode or GitHub

```bash
$ security find-generic-password -s "opencode" -a "$(whoami)"
# Returns: No opencode keychain entries found

$ security find-generic-password -s "github" -a "$(whoami)"
# Returns: No github keychain entries found
```

**Implication**: OpenCode stores credentials in plaintext JSON files, not in the system keychain. This is less secure than keychain storage but simplifies cross-platform compatibility.

## 7. Environment Variables

Only one environment variable is set by default:
```
OPENCODE=1
```

No GitHub or Copilot-specific environment variables are set. Authentication relies on the stored auth.json file.

**Supported for other providers:**
- AWS_ACCESS_KEY_ID
- AWS_SECRET_ACCESS_KEY  
- AWS_REGION

## 8. Configuration Example

### Main Config File (`~/.config/opencode/config.json`)

```json
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {},
  "model": "github-copilot/claude-sonnet-4.5",
  "small_model": "github-copilot/claude-haiku-4.5",
  "agent": {
    "build": {
      "mode": "primary",
      "model": "github-copilot/claude-sonnet-4.5",
      "prompt": "{file:./prompts/build.txt}",
      "tools": {
        "write": true,
        "edit": true,
        "bash": true
      }
    },
    // ... more agent configurations
  }
}
```

## 9. OpenCode Package Information

```
Package: opencode
Version: 1.1.57
Installation: /opt/homebrew/Cellar/opencode/1.1.57/
Type: Binary (Mach-O 64-bit arm64)
Dependencies: node, ripgrep
License: MIT
Source: https://github.com/Homebrew/homebrew-core (Homebrew formula)
```

## 10. Authentication Command Reference

```bash
# List current authentication providers
opencode auth list

# Login to a provider (GitHub Copilot)
opencode auth login github-copilot

# Logout from a provider
opencode auth logout

# List available models for a provider
opencode models github-copilot
```

## Recommendations for LogAI Implementation

### 1. **Authentication Architecture**
- Implement OAuth token storage in `~/.local/share/logai/auth.json`
- Follow the same JSON structure with `type`, `access`, `refresh`, `expires` fields
- Support Bearer token authentication in API headers

### 2. **Configuration Storage**
- Follow XDG Base Directory specification
- Separate concerns: config, state, cache, and data
- Store model preferences in main config file

### 3. **API Integration**
```javascript
// Pseudocode for API implementation
const token = readAuthFile('github-copilot').access;
const response = await fetch('https://api.githubcopilot.com/chat/completions', {
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    model: 'github-copilot/claude-sonnet-4.5',
    messages: [...],
    // ... other parameters
  })
});
```

### 4. **Model Provider String Format**
- Use `{provider}/{model}` format (e.g., `github-copilot/claude-sonnet-4.5`)
- Store provider and model separately in config
- Support dynamic model discovery via `opencode models {provider}`

### 5. **Security Considerations**
- Current OpenCode approach stores tokens in plaintext JSON
- For LogAI, consider implementing:
  - macOS Keychain integration for sensitive platforms
  - Environment variable support as fallback
  - Permission-restricted file access (600 on auth.json)
  - Encryption at rest for sensitive data

### 6. **CLI Commands to Implement**
```bash
logai auth login [provider]      # Interactive OAuth flow
logai auth logout                 # Remove credentials
logai auth list                  # Show authenticated providers
logai models [provider]          # List available models
logai config get/set             # Manage configuration
```

### 7. **File Structure for LogAI**
```
~/.config/logai/
├── config.json              # Main configuration
├── config.json.schema       # Config schema reference
└── prompts/                 # Custom prompts

~/.local/share/logai/
├── auth.json               # OAuth credentials
├── storage/
│   ├── message/            # Message history
│   ├── session/            # Session data
│   └── cache/              # Cache files
└── snapshot/               # Session snapshots

~/.local/state/logai/
└── model.json             # Recent model usage

~/.cache/logai/
└── tmp/                   # Temporary files
```

## References

- **OpenCode Repository**: https://github.com/opencode-ai/opencode
- **GitHub Copilot API Docs**: https://docs.github.com/en/copilot/using-github-copilot/getting-started-with-github-copilot
- **GitHub OAuth Documentation**: https://docs.github.com/en/developers/apps/building-oauth-apps
- **XDG Base Directory**: https://specifications.freedesktop.org/basedir-spec/basedir-spec-latest.html

---

**Investigation Date**: February 11, 2026
**Investigator**: Hans (Code Librarian)
**Status**: Complete
