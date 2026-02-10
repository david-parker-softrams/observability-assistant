# Using LogAI with Ollama (Local Models)

This guide explains how to use LogAI with local Ollama models for privacy-focused, cost-free log analysis.

## Benefits of Using Ollama

- 🔒 **Privacy**: Your logs never leave your machine
- 💰 **Cost**: No API fees
- 🌐 **Offline**: Works without internet connection
- 🧪 **Experimentation**: Try different models easily

## Prerequisites

- **RAM**: At least 8GB for 8B models, 32GB+ for 70B models
- **Disk**: ~4-40GB depending on model size
- **macOS, Linux, or Windows** with Ollama installed

## Installation Steps

### 1. Install Ollama

#### macOS
```bash
brew install ollama
```

#### Linux
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

#### Windows
Download from [https://ollama.ai](https://ollama.ai) and follow the installation wizard.

### 2. Choose a Model

LogAI requires models with **function calling support**. Recommended models:

| Model | Size | RAM Required | Performance |
|-------|------|--------------|-------------|
| `llama3.1:8b` | ~4.7GB | 8GB | Good for basic queries |
| `llama3.1:70b` | ~40GB | 48GB | Excellent for complex analysis |
| `mistral:latest` | ~4.1GB | 8GB | Good balance |

### 3. Pull Your Model

```bash
# Recommended for most users (8B model)
ollama pull llama3.1:8b

# For better performance (requires more RAM)
ollama pull llama3.1:70b

# Alternative model
ollama pull mistral
```

### 4. Start Ollama Server

```bash
ollama serve
```

The server will start on `http://localhost:11434` by default.

**Note**: On macOS and Windows with the desktop app, the server starts automatically.

### 5. Configure LogAI

Edit your `.env` file:

```bash
# Set Ollama as your LLM provider
LOGAI_LLM_PROVIDER=ollama

# Ollama base URL (default: http://localhost:11434)
LOGAI_OLLAMA_BASE_URL=http://localhost:11434

# Model to use (must support function calling)
LOGAI_OLLAMA_MODEL=llama3.1:8b

# AWS Configuration (still required for CloudWatch)
AWS_DEFAULT_REGION=us-east-1
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
```

### 6. Test the Setup

Start LogAI:
```bash
logai
```

Try a simple query:
```
🗨️ List all my log groups
```

If everything is working, you should see your CloudWatch log groups!

## Troubleshooting

### Issue: Function calling not working

**Symptoms**: LogAI can't execute tools, returns errors about function calling

**Solution**: Make sure you're using a model that supports function calling:
- ✅ Llama 3.1 (8b, 70b)
- ✅ Mistral
- ❌ Older Llama models (2, 3.0)
- ❌ Some smaller specialized models

```bash
# Check your model version
ollama list

# Upgrade to Llama 3.1 if needed
ollama pull llama3.1:8b
```

### Issue: Ollama connection refused

**Symptoms**: Error connecting to `http://localhost:11434`

**Solution**: Make sure Ollama server is running:

```bash
# Check if Ollama is running
curl http://localhost:11434/api/version

# If not, start the server
ollama serve
```

On macOS/Windows with desktop app, ensure the app is running in the background.

### Issue: Model performance is poor

**Symptoms**: Slow responses, incorrect analysis, missed patterns

**Solution**: Try these options in order:

1. **Use a larger model**:
```bash
ollama pull llama3.1:70b
# Update .env
LOGAI_OLLAMA_MODEL=llama3.1:70b
```

2. **Check system resources**:
```bash
# Make sure you have enough RAM
# 8B models need ~8GB
# 70B models need ~48GB
```

3. **Consider cloud providers**: For complex log analysis, cloud models (Claude, GPT-4) generally outperform local models.

### Issue: Out of memory errors

**Symptoms**: Ollama crashes or system becomes unresponsive

**Solution**: Use a smaller model or increase system RAM:

```bash
# Switch to 8B model
ollama pull llama3.1:8b
LOGAI_OLLAMA_MODEL=llama3.1:8b

# Or try Mistral (smaller)
ollama pull mistral
LOGAI_OLLAMA_MODEL=mistral
```

### Issue: Ollama not found in PATH

**Symptoms**: `ollama: command not found`

**Solution**: 
- **macOS**: Reinstall with `brew install ollama`
- **Linux**: Ensure `/usr/local/bin` is in your PATH
- **Windows**: Restart terminal after installation

## Performance Notes

### 8B Models (e.g., llama3.1:8b)
- **Pros**: Fast, low memory usage, good for basic queries
- **Cons**: May struggle with complex log analysis, pattern recognition
- **Best for**: Simple queries, testing, development

### 70B Models (e.g., llama3.1:70b)
- **Pros**: Much better reasoning, handles complex queries well
- **Cons**: Requires significant RAM (48GB+), slower responses
- **Best for**: Production use, complex analysis, when privacy is critical

### Cloud Models (Claude, GPT-4)
- **Pros**: Best performance, most capable for complex analysis
- **Cons**: Costs money, requires internet, data leaves your machine
- **Best for**: Best analysis quality, when privacy is not a concern

## Remote Ollama Setup

You can also run Ollama on a remote server:

### On the server:
```bash
# Start Ollama with host binding
OLLAMA_HOST=0.0.0.0:11434 ollama serve
```

### In your .env:
```bash
LOGAI_OLLAMA_BASE_URL=http://your-server-ip:11434
```

**Security Note**: Only expose Ollama on trusted networks. Consider using SSH tunneling for secure remote access.

## Switching Between Providers

You can easily switch between Ollama and cloud providers:

```bash
# Use Ollama
LOGAI_LLM_PROVIDER=ollama

# Use Claude (fast, high quality)
LOGAI_LLM_PROVIDER=anthropic

# Use GPT-4 (fast, high quality)
LOGAI_LLM_PROVIDER=openai
```

No other changes needed - LogAI handles the rest!

## FAQ

**Q: Can I use multiple models simultaneously?**
A: No, LogAI uses one provider at a time. Change `LOGAI_LLM_PROVIDER` in `.env` to switch.

**Q: Do I still need AWS credentials with Ollama?**
A: Yes! Ollama only replaces the LLM provider. You still need AWS credentials to access CloudWatch logs.

**Q: Can I use custom/fine-tuned models?**
A: Yes! Any Ollama model with function calling support should work. Set `LOGAI_OLLAMA_MODEL` to your model name.

**Q: How much does Ollama cost?**
A: Ollama is completely free and open-source. You only pay for the hardware to run it.

**Q: Can I use Ollama in production?**
A: Yes, but consider:
- Hardware requirements (especially for 70B models)
- Performance vs. cloud models
- Your privacy requirements
- Availability needs (uptime, scaling)

## Additional Resources

- [Ollama Documentation](https://github.com/ollama/ollama)
- [Ollama Model Library](https://ollama.ai/library)
- [LogAI Documentation](../README.md)
- [LiteLLM Documentation](https://docs.litellm.ai/)

## Getting Help

If you encounter issues with Ollama support:

1. Check this troubleshooting guide
2. Verify your model supports function calling
3. Check Ollama server logs: `ollama logs`
4. Report issues on [GitHub](https://github.com/logai/logai/issues)

---

Made with ❤️ for privacy-focused log analysis
