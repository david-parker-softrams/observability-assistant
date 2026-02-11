# LogAI Terminal User Interface (TUI)

The LogAI TUI provides an interactive chat interface for querying AWS CloudWatch logs using natural language.

## Features

### Chat Interface
- **Real-time streaming**: Responses are streamed token-by-token for immediate feedback
- **Message history**: All conversation history is maintained during the session
- **Syntax highlighting**: Code blocks and log excerpts are properly formatted
- **Error handling**: Clear error messages with helpful suggestions

### Special Commands
- `/help` - Show available commands and usage tips
- `/clear` - Clear conversation history
- `/cache status` - Display cache statistics (hits, misses, size)
- `/cache clear` - Clear the cache
- `/model` - Show current LLM model information
- `/config` - Display current configuration
- `/quit` or `/exit` - Exit the application (or use Ctrl+C)

### Status Bar
The bottom status bar shows:
- **Status**: Current application state (Ready, Thinking, Error)
- **Cache stats**: Cache hits and hit rate
- **Model**: Current LLM model in use

### Keyboard Shortcuts
- **Enter**: Send message
- **Ctrl+C** or **Ctrl+Q**: Quit application

## Usage

Start the TUI:
```bash
logai
```

With AWS profile and region options:
```bash
# Use specific AWS profile
logai --aws-profile prod

# Specify profile and region
logai --aws-profile prod --aws-region us-west-2
```

The application will:
1. Load and validate configuration (including CLI arguments)
2. Initialize all components (LLM, CloudWatch, cache)
3. Launch the interactive chat interface

See the [README](../README.md#-command-line-arguments) for more details on CLI arguments.

## Architecture

### Components

#### `ui/app.py` - Main Application
- Entry point for the TUI
- Manages application lifecycle
- Handles shutdown and cleanup

#### `ui/screens/chat.py` - Chat Screen
- Main chat interface layout
- Handles user input and message display
- Coordinates with orchestrator for LLM interactions
- Manages message streaming and updates

#### `ui/widgets/messages.py` - Message Widgets
- `UserMessage`: User messages (right-aligned, blue)
- `AssistantMessage`: AI responses (left-aligned, gray)
- `SystemMessage`: System notifications (centered, dimmed)
- `LoadingIndicator`: "Thinking..." indicator
- `ErrorMessage`: Error displays (red background)

#### `ui/widgets/input_box.py` - Input Widget
- Text input for user messages
- Enter to send, Ctrl+C to quit

#### `ui/widgets/status_bar.py` - Status Bar
- Reactive status updates
- Cache statistics display
- Model information

#### `ui/commands.py` - Command Handler
- Processes special slash commands
- Provides help and configuration info
- Manages cache operations

### Message Flow

1. User types message and presses Enter
2. `ChatScreen` receives input event
3. If command (starts with `/`):
   - `CommandHandler` processes the command
   - Response displayed as system message
4. If normal message:
   - Message added to chat as `UserMessage`
   - `LoadingIndicator` displayed
   - `LLMOrchestrator.chat_stream()` called
   - Tokens streamed to `AssistantMessage`
   - Cache stats updated
   - Status bar reflects new state

### Styling

The TUI uses Textual CSS (TCSS) for styling:
- `ui/styles/app.tcss` - Main stylesheet
- Responsive design that adapts to terminal size
- Professional color scheme with good contrast
- Distinct styling for different message types

## Testing

Unit tests for UI components:
```bash
pytest tests/unit/test_ui_widgets.py -v
pytest tests/unit/test_commands.py -v
```

## Example Session

```
LogAI v0.1.0
✓ LLM Provider: anthropic
✓ LLM Model: claude-3-5-sonnet-20241022
✓ AWS Region: us-east-1 (from environment/default)
✓ AWS Profile: prod (from CLI argument)
✓ PII Sanitization: Enabled
✓ Cache Directory: /Users/user/.logai/cache

┌─────────────────────────────────────────┐
│         LogAI - CloudWatch Assistant     │
├─────────────────────────────────────────┤
│                                          │
│  [System] Welcome to LogAI! Ask me       │
│  about your AWS CloudWatch logs.         │
│                                          │
│  You: Show me errors from the last hour  │
│                                          │
│  Assistant: I'll help you find errors... │
│  Let me fetch the log groups first.      │
│                                          │
├─────────────────────────────────────────┤
│ > Type your message here...              │
├─────────────────────────────────────────┤
│ Status: Ready | Cache: 0 hits | Model:   │
│ claude-3-5-sonnet-20241022               │
└─────────────────────────────────────────┘
```

## Future Enhancements (Post-MVP)

- **Split panes**: Log viewer panel alongside chat
- **Syntax highlighting**: Rich formatting for JSON logs
- **Input history**: Up/down arrows to navigate previous messages
- **Markdown rendering**: Full markdown support in responses
- **Session persistence**: Save and resume conversations
- **Export**: Save conversation to file
- **Themes**: Customizable color schemes
