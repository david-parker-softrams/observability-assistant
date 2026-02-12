# LogAI GitHub Copilot Integration - Implementation Roadmap

## Quick Reference: What We Learned from OpenCode

| Aspect | OpenCode Implementation | Recommendation for LogAI |
|--------|-------------------------|--------------------------|
| **Auth Storage** | `~/.local/share/opencode/auth.json` | Use same structure, different app name |
| **Auth Type** | OAuth 2.0 (Bearer tokens) | Implement same pattern |
| **API Endpoint** | `https://api.githubcopilot.com/chat/completions` | Same endpoint (GitHub-provided) |
| **Token Format** | `gho_XXXXX...` | GitHub standard, no modification needed |
| **Config Storage** | `~/.config/opencode/config.json` | Follow XDG spec, same location pattern |
| **Configuration Validation** | JSON Schema (`opencode.ai/config.json`) | Create similar schema for LogAI |
| **Model Format** | `{provider}/{model}` | Adopt same convention |
| **Session Storage** | JSONL files in `~/.local/share/` | Similar approach works well |
| **Keychain Integration** | None (plaintext JSON) | Consider improving with keychain for security |
| **File Permissions** | 644 (world-readable) | **Improve to 600** for auth.json |

## Phase 1: Foundation (Week 1)

### 1.1 Directory Structure Setup
```bash
# Create directory structure
mkdir -p ~/.config/logai
mkdir -p ~/.local/share/logai/{storage/{message,session,session_diff},snapshot,log}
mkdir -p ~/.local/state/logai
mkdir -p ~/.cache/logai
```

### 1.2 Configuration File Creation
**File**: `~/.config/logai/config.json`

```json
{
  "$schema": "https://logai.dev/config.json",
  "provider": {},
  "model": "github-copilot/claude-sonnet-4.5",
  "small_model": "github-copilot/claude-haiku-4.5",
  "agent": {
    "default": {
      "model": "github-copilot/claude-sonnet-4.5",
      "temperature": 0.5,
      "tools": {
        "read": true,
        "grep": true,
        "bash": true
      }
    }
  }
}
```

### 1.3 Auth File Structure
**File**: `~/.local/share/logai/auth.json` (create with `chmod 600`)

```json
{
  "github-copilot": {
    "type": "oauth",
    "access": "",
    "refresh": "",
    "expires": 0
  }
}
```

## Phase 2: Authentication Module (Week 2)

### 2.1 Core Auth Interface

```typescript
// src/auth/types.ts
export interface AuthConfig {
  type: 'oauth' | 'pat' | 'env';
  access: string;
  refresh?: string;
  expires?: number;
  provider?: string;
}

export interface AuthProvider {
  authenticate(): Promise<void>;
  isAuthenticated(): boolean;
  getToken(): string;
  refreshToken(): Promise<void>;
  logout(): Promise<void>;
}

export interface ProviderCredentials {
  [provider: string]: AuthConfig;
}
```

### 2.2 Authentication Manager

```typescript
// src/auth/AuthManager.ts
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

export class AuthManager {
  private authFilePath: string;
  private credentials: ProviderCredentials = {};

  constructor() {
    this.authFilePath = path.join(
      os.homedir(),
      '.local/share/logai/auth.json'
    );
  }

  // Load credentials from disk
  loadCredentials(): void {
    try {
      const data = fs.readFileSync(this.authFilePath, 'utf-8');
      this.credentials = JSON.parse(data);
    } catch (error) {
      // File doesn't exist or is invalid - initialize empty
      this.credentials = {};
    }
  }

  // Save credentials to disk with restricted permissions
  saveCredentials(provider: string, config: AuthConfig): void {
    this.credentials[provider] = config;
    
    // Create directory if it doesn't exist
    const dir = path.dirname(this.authFilePath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }

    // Write with 600 permissions (owner-only)
    fs.writeFileSync(
      this.authFilePath,
      JSON.stringify(this.credentials, null, 2),
      { mode: 0o600 }
    );
  }

  // Get token for provider
  getToken(provider: string): string {
    const config = this.credentials[provider];
    if (!config) {
      throw new Error(`No credentials found for provider: ${provider}`);
    }
    return config.access;
  }

  // Check if authenticated
  isAuthenticated(provider: string): boolean {
    return !!(this.credentials[provider]?.access);
  }

  // List authenticated providers
  listProviders(): string[] {
    return Object.keys(this.credentials);
  }
}
```

### 2.3 GitHub Copilot Provider Implementation

```typescript
// src/auth/GitHubCopilotProvider.ts
import { AuthProvider, AuthConfig } from './types';
import axios, { AxiosInstance } from 'axios';

export class GitHubCopilotProvider implements AuthProvider {
  private token: string = '';
  private apiEndpoint = 'https://api.githubcopilot.com/chat/completions';
  private client: AxiosInstance;

  constructor(token?: string) {
    if (token) this.token = token;
    this.client = axios.create({
      baseURL: 'https://api.githubcopilot.com'
    });
  }

  async authenticate(): Promise<void> {
    // OAuth flow - would need interactive browser component
    // For now, require token to be set via auth.json
    if (!this.token) {
      throw new Error('GitHub Copilot authentication required');
    }
  }

  isAuthenticated(): boolean {
    return !!this.token;
  }

  getToken(): string {
    return this.token;
  }

  setToken(token: string): void {
    this.token = token;
  }

  async refreshToken(): Promise<void> {
    // GitHub Copilot tokens might not need refresh
    // Keep for future compatibility
    console.log('Token refresh not yet implemented');
  }

  async logout(): Promise<void> {
    this.token = '';
  }

  // Make API request
  async request(model: string, messages: Message[]): Promise<Response> {
    if (!this.isAuthenticated()) {
      throw new Error('Not authenticated');
    }

    const response = await this.client.post<Response>(
      '/chat/completions',
      {
        model,
        messages,
        temperature: 0.3,
        max_tokens: 4096
      },
      {
        headers: {
          'Authorization': `Bearer ${this.token}`,
          'Content-Type': 'application/json'
        }
      }
    );

    return response.data;
  }
}
```

## Phase 3: Configuration Management (Week 2)

### 3.1 Config Manager

```typescript
// src/config/ConfigManager.ts
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

export interface LogAIConfig {
  $schema?: string;
  provider: Record<string, unknown>;
  model: string;
  small_model: string;
  agent?: Record<string, AgentConfig>;
}

export interface AgentConfig {
  model: string;
  temperature?: number;
  tools?: {
    [key: string]: boolean;
  };
}

export class ConfigManager {
  private configPath: string;
  private config: LogAIConfig;

  constructor() {
    this.configPath = path.join(
      os.homedir(),
      '.config/logai/config.json'
    );
    this.loadConfig();
  }

  private loadConfig(): void {
    try {
      const data = fs.readFileSync(this.configPath, 'utf-8');
      this.config = JSON.parse(data);
    } catch (error) {
      // Use default config
      this.config = this.getDefaultConfig();
    }
  }

  private getDefaultConfig(): LogAIConfig {
    return {
      $schema: 'https://logai.dev/config.json',
      provider: {},
      model: 'github-copilot/claude-sonnet-4.5',
      small_model: 'github-copilot/claude-haiku-4.5',
      agent: {}
    };
  }

  getModel(): string {
    return this.config.model;
  }

  getSmallModel(): string {
    return this.config.small_model;
  }

  getAgentConfig(agentName: string): AgentConfig | undefined {
    return this.config.agent?.[agentName];
  }

  saveConfig(): void {
    const dir = path.dirname(this.configPath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    fs.writeFileSync(
      this.configPath,
      JSON.stringify(this.config, null, 2)
    );
  }

  setModel(model: string): void {
    this.config.model = model;
    this.saveConfig();
  }
}
```

## Phase 4: API Integration (Week 3)

### 4.1 Model Provider Interface

```typescript
// src/providers/ModelProvider.ts
export interface Message {
  role: 'system' | 'user' | 'assistant';
  content: string;
}

export interface ModelResponse {
  id: string;
  model: string;
  choices: {
    index: number;
    message: Message;
    finish_reason: string;
  }[];
  usage: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
}

export interface ModelProvider {
  sendMessage(messages: Message[]): Promise<ModelResponse>;
  getAvailableModels(): Promise<string[]>;
}
```

### 4.2 GitHub Copilot Model Provider

```typescript
// src/providers/GitHubCopilotModelProvider.ts
import { GitHubCopilotProvider } from '../auth/GitHubCopilotProvider';
import { ModelProvider, Message, ModelResponse } from './ModelProvider';

export class GitHubCopilotModelProvider implements ModelProvider {
  constructor(
    private authProvider: GitHubCopilotProvider,
    private model: string
  ) {}

  async sendMessage(messages: Message[]): Promise<ModelResponse> {
    return this.authProvider.request(this.model, messages);
  }

  async getAvailableModels(): Promise<string[]> {
    // Return known models - could be fetched from API
    return [
      'github-copilot/claude-haiku-4.5',
      'github-copilot/claude-sonnet-4.5',
      'github-copilot/claude-opus-4.5',
      'github-copilot/gpt-4.1',
      'github-copilot/gpt-4o',
      'github-copilot/gemini-2.5-pro'
    ];
  }
}
```

## Phase 5: CLI Commands (Week 3-4)

### 5.1 Auth Commands

```bash
# Authentication management
logai auth login [provider]      # Authenticate with GitHub Copilot
logai auth logout [provider]     # Remove credentials
logai auth list                  # List authenticated providers
logai auth status                # Show current authentication status
```

### 5.2 Configuration Commands

```bash
# Configuration management
logai config show                # Display current configuration
logai config get [key]           # Get configuration value
logai config set [key] [value]   # Set configuration value
logai config reset               # Reset to default configuration
```

### 5.3 Model Commands

```bash
# Model management
logai models                     # List available models
logai models [provider]          # List models for provider
logai model [provider/model]     # Set default model
```

## Phase 6: Session & History (Week 4)

### 6.1 Session Storage

```typescript
// src/session/SessionManager.ts
export interface Session {
  id: string;
  created: number;
  updated: number;
  messages: Message[];
  model: string;
  metadata?: Record<string, unknown>;
}

export class SessionManager {
  private storageDir: string;

  constructor() {
    this.storageDir = path.join(
      os.homedir(),
      '.local/share/logai/storage/session'
    );
  }

  saveSession(session: Session): void {
    const sessionPath = path.join(this.storageDir, `${session.id}.json`);
    fs.writeFileSync(sessionPath, JSON.stringify(session, null, 2));
  }

  loadSession(id: string): Session | null {
    const sessionPath = path.join(this.storageDir, `${id}.json`);
    try {
      const data = fs.readFileSync(sessionPath, 'utf-8');
      return JSON.parse(data);
    } catch {
      return null;
    }
  }

  listSessions(): string[] {
    return fs.readdirSync(this.storageDir)
      .filter(f => f.endsWith('.json'))
      .map(f => f.replace('.json', ''));
  }
}
```

## Phase 7: Testing & Documentation (Week 4)

### 7.1 Test Structure

```typescript
// test/auth/AuthManager.test.ts
import { AuthManager } from '../../src/auth/AuthManager';

describe('AuthManager', () => {
  it('should save and load credentials', () => {
    const manager = new AuthManager();
    const config = {
      type: 'oauth' as const,
      access: 'test-token'
    };
    
    manager.saveCredentials('github-copilot', config);
    manager.loadCredentials();
    
    expect(manager.getToken('github-copilot')).toBe('test-token');
  });

  it('should handle missing credentials gracefully', () => {
    const manager = new AuthManager();
    manager.loadCredentials();
    
    expect(manager.isAuthenticated('unknown')).toBe(false);
  });
});
```

## Implementation Checklist

### Phase 1: Foundation
- [ ] Create directory structure
- [ ] Set up config.json template
- [ ] Create auth.json template with 600 permissions
- [ ] Document XDG directory usage

### Phase 2: Authentication
- [ ] Implement AuthManager class
- [ ] Implement GitHubCopilotProvider class
- [ ] Write unit tests for auth module
- [ ] Create auth CLI commands

### Phase 3: Configuration
- [ ] Implement ConfigManager class
- [ ] Create config.json schema
- [ ] Write unit tests for config module
- [ ] Create config CLI commands

### Phase 4: API Integration
- [ ] Implement ModelProvider interface
- [ ] Implement GitHubCopilotModelProvider
- [ ] Add error handling and retry logic
- [ ] Test API integration

### Phase 5: CLI
- [ ] Implement auth commands
- [ ] Implement config commands
- [ ] Implement model commands
- [ ] Add help documentation

### Phase 6: Session Management
- [ ] Implement SessionManager
- [ ] Create session storage structure
- [ ] Add session list/load/save commands
- [ ] Test session persistence

### Phase 7: Testing & Docs
- [ ] Write comprehensive unit tests
- [ ] Create API documentation
- [ ] Create user guide
- [ ] Create architecture documentation

## Security Recommendations

1. **File Permissions**
   ```bash
   chmod 600 ~/.local/share/logai/auth.json
   ```

2. **Token Rotation**
   - Implement periodic token refresh
   - Monitor token expiration
   - Log token usage

3. **Environment Variables**
   - Support `LOGAI_GITHUB_COPILOT_TOKEN` as fallback
   - Support `LOGAI_CONFIG_DIR` for custom config location

4. **Keychain Integration (Future)**
   ```typescript
   // On macOS, use Keychain for token storage
   import keytar from 'keytar';
   
   // Store token in keychain
   await keytar.setPassword('logai', 'github-copilot', token);
   
   // Retrieve token from keychain
   const token = await keytar.getPassword('logai', 'github-copilot');
   ```

## Performance Considerations

1. **Lazy Loading**
   - Load auth only when needed
   - Cache config in memory
   - Implement LRU cache for API responses

2. **Error Handling**
   - Implement exponential backoff for rate limits
   - Cache failed responses briefly
   - Provide clear error messages

3. **Token Management**
   - Validate token before each request
   - Cache token validity status
   - Implement request deduplication

## Dependencies to Add

```json
{
  "dependencies": {
    "axios": "^1.6.0",
    "dotenv": "^16.0.0",
    "zod": "^3.20.0"
  },
  "devDependencies": {
    "@types/node": "^20.0.0",
    "jest": "^29.0.0",
    "ts-jest": "^29.0.0",
    "typescript": "^5.0.0"
  }
}
```

## References for Implementation

- [OpenCode Repository](https://github.com/opencode-ai/opencode)
- [GitHub Copilot API Documentation](https://docs.github.com/en/copilot)
- [XDG Base Directory Specification](https://specifications.freedesktop.org/basedir-spec/)
- [OpenAI API Integration Patterns](https://platform.openai.com/docs/api-reference)

---

**Prepared by**: Hans (Code Librarian)
**Date**: February 11, 2026
**Status**: Ready for Development
