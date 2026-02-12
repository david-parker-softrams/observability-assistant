# OpenCode GitHub Copilot Integration - Technical Deep Dive

## Authentication Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         USER AUTHENTICATION FLOW                         │
└─────────────────────────────────────────────────────────────────────────┘

┌──────────────┐
│ User runs:   │
│ opencode auth│
│ login        │
└──────┬───────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────────┐
│ Step 1: OpenCode initiates OAuth flow                               │
│ - Launches browser or displays auth URL                             │
│ - User authenticates with GitHub account                            │
│ - GitHub returns authorization code                                 │
└──────┬───────────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────────┐
│ Step 2: OpenCode exchanges code for token                           │
│ - Sends auth code to GitHub OAuth endpoint                          │
│ - Receives: access_token (gho_XXXXX), refresh_token                │
└──────┬───────────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────────┐
│ Step 3: Store credentials locally                                   │
│ Location: ~/.local/share/opencode/auth.json                         │
│ Structure:                                                           │
│ {                                                                    │
│   "github-copilot": {                                               │
│     "type": "oauth",                                                │
│     "access": "gho_XXXXX...",                                       │
│     "refresh": "gho_XXXXX...",                                      │
│     "expires": 0                                                     │
│   }                                                                  │
│ }                                                                    │
└──────┬───────────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────────┐
│ User now authenticated and can use OpenCode                          │
└─────────────────────────────────────────────────────────────────────┘
```

## Model Request Flow

```
┌──────────────────────────────────────────────────────────────────────┐
│                      MODEL INFERENCE REQUEST FLOW                    │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────┐
│ User Request:    │
│ opencode run     │
│ "write a func"   │
└──────┬───────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────────┐
│ Step 1: OpenCode loads configuration                                │
│ Config: ~/.config/opencode/config.json                              │
│ - Default model: github-copilot/claude-sonnet-4.5                   │
│ - Small model: github-copilot/claude-haiku-4.5                      │
└──────┬───────────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────────┐
│ Step 2: Load authentication token                                   │
│ Source: ~/.local/share/opencode/auth.json                           │
│ Extract: github-copilot.access (Bearer token)                       │
└──────┬───────────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────────┐
│ Step 3: Construct API request                                       │
│                                                                      │
│ POST https://api.githubcopilot.com/chat/completions               │
│ Headers:                                                             │
│   Authorization: Bearer gho_XXXXX...                               │
│   Content-Type: application/json                                    │
│                                                                      │
│ Body (JSON):                                                         │
│ {                                                                    │
│   "model": "claude-sonnet-4.5",                                    │
│   "messages": [                                                      │
│     {"role": "system", "content": "..."},                           │
│     {"role": "user", "content": "write a func"}                     │
│   ],                                                                 │
│   "temperature": 0.3,                                               │
│   "top_p": 1.0,                                                     │
│   "max_tokens": 4096                                                │
│ }                                                                    │
└──────┬───────────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────────┐
│ Step 4: GitHub Copilot API processes request                        │
│ - Validates Bearer token                                             │
│ - Routes to appropriate model backend                               │
│ - Model inference (Claude, GPT, Gemini, etc)                        │
│ - Returns response                                                   │
└──────┬───────────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────────┐
│ Step 5: Store response and metadata                                 │
│ Location: ~/.local/share/opencode/storage/                          │
│ - Message history: storage/message/                                 │
│ - Session data: storage/session/                                    │
│ - Session diffs: storage/session_diff/                              │
└──────┬───────────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────────┐
│ Return response to user                                              │
└──────────────────────────────────────────────────────────────────────┘
```

## File System Structure (Complete Mapping)

```
~/.config/opencode/
├── config.json                    # Main configuration file
│   ├── $schema: https://opencode.ai/config.json
│   ├── provider: {}              # Provider-specific settings
│   ├── model: github-copilot/claude-sonnet-4.5
│   ├── small_model: github-copilot/claude-haiku-4.5
│   └── agent: { }                # Agent configurations
├── node_modules/                 # Installed dependencies
│   ├── @opencode-ai/
│   │   ├── plugin/
│   │   └── sdk/
│   └── zod/                      # Validation library
└── package.json

~/.local/share/opencode/
├── auth.json                      # OAuth credentials (SENSITIVE)
│   └── github-copilot:
│       ├── type: "oauth"
│       ├── access: "gho_..."
│       ├── refresh: "gho_..."
│       └── expires: 0
├── storage/                       # Persistent storage
│   ├── message/                  # Chat message history
│   │   └── ses_{sessionID}/
│   │       └── msg_{msgID}.json
│   ├── session/                  # Session metadata
│   │   └── {sessionID}/
│   │       ├── metadata.json
│   │       └── config.json
│   ├── session_diff/             # Session diff tracking
│   │   └── {diffID}/
│   ├── part/                     # Part storage (1069+ parts)
│   │   └── part_{ID}.json
│   ├── project/                  # Project metadata
│   └── todo/                     # Todo items
├── snapshot/                      # Session snapshots
│   └── {snapshotID}/
│       ├── index                 # Binary index
│       └── data/
├── log/                          # Application logs
│   ├── combined.log
│   ├── error.log
│   ├── debug.log
│   └── {date}.log
└── (other supporting files)

~/.local/state/opencode/
├── model.json                     # Recent model usage
│   ├── recent: [
│   │   {providerID: "github-copilot", modelID: "claude-opus-4.6"},
│   │   {providerID: "github-copilot", modelID: "claude-opus-4.5"},
│   │   {providerID: "github-copilot", modelID: "claude-sonnet-4.5"}
│   │ ]
│   ├── favorite: []
│   └── variant: {}
└── prompt-history.jsonl          # Prompt history (JSONL format)

~/.cache/opencode/
└── (cache files if used)
```

## API Request/Response Examples

### Minimal Request Example

```json
POST https://api.githubcopilot.com/chat/completions
Authorization: Bearer gho_XXXXXXXXXXXXXXXXXXXXXXXXXXXXX

{
  "model": "claude-sonnet-4.5",
  "messages": [
    {
      "role": "system",
      "content": "You are a helpful coding assistant."
    },
    {
      "role": "user",
      "content": "Write a hello world function in Python"
    }
  ]
}
```

### Response Format (OpenAI-Compatible)

```json
{
  "id": "chatcmpl-8Q3Z3ZJ0Q0Q0Q0Q0Q0Q0",
  "object": "chat.completion",
  "created": 1707582200,
  "model": "claude-sonnet-4.5",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Here's a simple hello world function in Python:\n\n```python\ndef hello_world():\n    print('Hello, World!')\n\nhello_world()\n```"
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 42,
    "completion_tokens": 35,
    "total_tokens": 77
  }
}
```

## Token Management

### Token Format
- **Prefix**: `gho_` (GitHub OAuth token)
- **Length**: Typically 36-40 characters after prefix
- **Type**: GitHub Personal Access Token (PAT)
- **Scope**: Full access to GitHub Copilot API

### Token Storage Security
```
File: ~/.local/share/opencode/auth.json
Permissions: Typically 644 (world-readable) - SECURITY RISK
Sensitive: YES - Contains OAuth token
Recommended: Should be 600 (owner-only)
Encryption: NONE - Plaintext JSON
Keychain: NO - Not stored in macOS keychain
```

### Token Refresh Logic
```
expires: 0 means:
- No automatic refresh
- Token is valid indefinitely
- Manual rotation may be required
- OR GitHub tokens don't expire in this implementation
```

## Model Selection Hierarchy

OpenCode uses this priority for model selection:

1. **Command-line override**: `opencode -m github-copilot/claude-opus-4.5`
2. **Agent-specific config**: Each agent has a configured model
3. **Default model**: From config.json "model" field
4. **Fallback**: claude-sonnet-4.5

### Agent Model Mapping (from config)
```
build           → github-copilot/claude-sonnet-4.5      (most capable)
explore         → github-copilot/claude-haiku-4.5       (fast)
librarian       → github-copilot/claude-haiku-4.5       (fast)
plan            → github-copilot/claude-haiku-4.5       (fast)
code-reviewer   → github-copilot/claude-sonnet-4.5      (quality)
software-architect → github-copilot/claude-opus-4.5    (most capable)
software-engineer  → github-copilot/claude-sonnet-4.5  (balanced)
qa-engineer     → github-copilot/claude-sonnet-4.5      (thorough)
tech-writer     → github-copilot/claude-sonnet-4.5      (quality)
```

## Error Handling & Edge Cases

### Common Authentication Errors

1. **No credentials stored**
   ```
   Error: No github-copilot credentials found
   Solution: Run `opencode auth login github-copilot`
   ```

2. **Expired or revoked token**
   ```
   Response: 401 Unauthorized
   Solution: Re-authenticate or refresh token
   ```

3. **Rate limiting**
   ```
   Response: 429 Too Many Requests
   Mitigation: Implement exponential backoff
   ```

### Configuration Validation

- Config schema: https://opencode.ai/config.json
- OpenCode validates config against schema on startup
- Invalid config → Error message + default behavior

## Recommended Implementation Pattern for LogAI

```typescript
// Pseudocode for LogAI implementation

interface AuthConfig {
  type: 'oauth';
  access: string;
  refresh: string;
  expires: number;
}

interface ModelRequest {
  provider: string;      // "github-copilot"
  model: string;         // "claude-sonnet-4.5"
  messages: Message[];
  temperature?: number;
  max_tokens?: number;
}

class GitHubCopilotProvider {
  private authToken: string;
  private apiEndpoint = 'https://api.githubcopilot.com/chat/completions';
  
  async authenticate() {
    // 1. Read from ~/.local/share/logai/auth.json
    // 2. Validate token is not expired
    // 3. Set this.authToken
  }
  
  async request(modelRequest: ModelRequest) {
    // 1. Validate authentication
    // 2. Build request with Bearer token
    // 3. Send to GitHub Copilot API
    // 4. Handle response and errors
    // 5. Log to ~/.local/state/logai/model.json
  }
  
  async saveAuth(token: string) {
    // 1. Ensure ~/.local/share/logai/ exists
    // 2. Write auth.json with proper structure
    // 3. Set file permissions to 600
  }
}
```

---

**Last Updated**: February 11, 2026
**Investigator**: Hans (Code Librarian)
