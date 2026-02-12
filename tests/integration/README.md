# Integration Tests

This directory contains integration tests that verify end-to-end behavior of the LogAI system.

## Test Files

### `test_agent_retry_behavior.py`
Comprehensive integration tests for the agent self-direction and automatic retry system.

**Test Classes:**
- `TestEmptyResultsAutoRetry` - Tests automatic retry when encountering empty log results
- `TestIntentDetectionAndNudging` - Tests intent detection and agent nudging behavior
- `TestFeatureFlagBehavior` - Tests behavior with feature flags enabled/disabled
- `TestStrategyTracking` - Tests retry strategy tracking and deduplication
- `TestLogGroupNotFound` - Tests retry when log groups don't exist
- `TestComplexScenarios` - Tests complex multi-step retry scenarios

**Key Scenarios Covered:**
1. Empty logs trigger retry with expanded time range (max 3 attempts)
2. Intent stated without action triggers nudge to execute
3. Premature giving up triggers retry encouragement
4. Feature flags control retry behavior
5. Strategies are tracked to avoid duplication
6. Log group not found errors trigger alternative searches
7. Multiple failure types handled in sequence

### `test_intent_detection_e2e.py`
End-to-end tests for the intent detection system.

**Test Classes:**
- `TestIntentDetectionPatterns` - Tests various intent pattern recognition
- `TestIntentNudgingFlow` - Tests complete flow from intent to action
- `TestIntentWithRetry` - Tests interaction between intent detection and retry logic
- `TestEdgeCases` - Tests edge cases in intent detection

**Key Scenarios Covered:**
1. Detection of search, list, expand time, and filter change intents
2. Distinction between intent and analysis (no false positives)
3. Detection of premature giving up patterns
4. Complete nudging flow from intent to tool call
5. Multiple intents in single conversation
6. Intent detection after empty results
7. Max nudge attempts respected

## Running Integration Tests

### Run all integration tests:
```bash
pytest tests/integration/ -v
```

### Run specific test file:
```bash
pytest tests/integration/test_agent_retry_behavior.py -v
pytest tests/integration/test_intent_detection_e2e.py -v
```

### Run specific test class:
```bash
pytest tests/integration/test_agent_retry_behavior.py::TestEmptyResultsAutoRetry -v
```

### Run specific test:
```bash
pytest tests/integration/test_agent_retry_behavior.py::TestEmptyResultsAutoRetry::test_empty_logs_triggers_retry_with_expanded_time -v
```

### Run tests matching a pattern:
```bash
pytest tests/integration/ -k retry -v
pytest tests/integration/ -k intent -v
pytest tests/integration/ -k "empty or not_found" -v
```

### Run with coverage:
```bash
pytest tests/integration/ --cov=logai.core.orchestrator --cov=logai.core.intent_detector --cov-report=html
```

### Run with verbose output and logging:
```bash
pytest tests/integration/ -v -s --log-cli-level=INFO
```

## Test Architecture

### Fixtures
Integration tests use the following fixtures:
- `integration_settings` - Standard settings with self-direction enabled
- `disabled_retry_settings` - Settings with auto-retry disabled
- `e2e_settings` - Settings for end-to-end testing
- `mock_sanitizer` - Mock PII sanitizer
- Mock LLM providers and tool registries created per test

### Mocking Strategy
- **LLM Provider**: Mocked with `AsyncMock` to return predetermined responses
- **Tool Registry**: Mocked with `AsyncMock` to return test data
- **CloudWatch API**: Not called directly; tools are mocked at registry level
- **No external dependencies**: All tests run without network calls

### Test Pattern
Most integration tests follow this pattern:

1. **Setup**: Create mock LLM with sequence of expected responses
2. **Setup**: Create mock tools with sequence of expected results
3. **Execute**: Call orchestrator.chat() with test query
4. **Verify**: Assert tool call counts, arguments, and final response

Example:
```python
@pytest.mark.asyncio
async def test_scenario(self, integration_settings, mock_sanitizer):
    # Setup mocks
    mock_llm = AsyncMock()
    mock_llm.chat.side_effect = [
        LLMResponse(...),  # First response
        LLMResponse(...),  # Second response
    ]
    
    mock_tools = Mock(spec=ToolRegistry)
    mock_tools.execute = AsyncMock()
    mock_tools.execute.side_effect = [
        {...},  # First tool result
        {...},  # Second tool result
    ]
    
    # Create orchestrator
    orchestrator = LLMOrchestrator(
        llm_provider=mock_llm,
        tool_registry=mock_tools,
        sanitizer=mock_sanitizer,
        settings=integration_settings,
    )
    
    # Execute
    result = await orchestrator.chat("Test query")
    
    # Verify
    assert mock_tools.execute.call_count == 2
    assert "expected" in result
```

## Coverage Goals

Target coverage for integration tests:
- `orchestrator.py` retry logic: **90%+**
- `intent_detector.py`: **90%+**
- Retry state management: **100%**
- Retry prompt generation: **100%**

## Performance

Integration tests should be fast:
- **Individual test**: < 100ms
- **Full suite**: < 5 seconds

All tests use mocks and no I/O operations, ensuring fast execution.

## Debugging Failed Tests

### Enable detailed logging:
```bash
pytest tests/integration/test_agent_retry_behavior.py -v -s --log-cli-level=DEBUG
```

### Run single test with pdb:
```bash
pytest tests/integration/test_agent_retry_behavior.py::TestEmptyResultsAutoRetry::test_empty_logs_triggers_retry_with_expanded_time -v -s --pdb
```

### Check mock call details:
Add this to your test:
```python
print(f"LLM call count: {mock_llm.chat.call_count}")
print(f"LLM calls: {mock_llm.chat.call_args_list}")
print(f"Tool call count: {mock_tools.execute.call_count}")
print(f"Tool calls: {mock_tools.execute.call_args_list}")
```

## Adding New Tests

When adding new integration tests:

1. **Choose appropriate test file**:
   - Retry behavior → `test_agent_retry_behavior.py`
   - Intent detection → `test_intent_detection_e2e.py`

2. **Use existing fixtures** for consistency

3. **Follow naming convention**:
   - `test_<scenario>_<expected_behavior>`
   - Example: `test_empty_logs_triggers_retry_with_expanded_time`

4. **Document test purpose** with clear docstring

5. **Keep tests focused**: One scenario per test

6. **Use parametrize** for similar scenarios with different inputs

7. **Update this README** with new test coverage

## Common Issues

### Issue: Test hangs
**Cause**: LLM mock not providing enough responses for conversation loop  
**Fix**: Add more responses to `mock_llm.chat.side_effect` list

### Issue: Assertion error on call count
**Cause**: Retry logic behavior changed  
**Fix**: Review orchestrator changes and update expected call counts

### Issue: "AttributeError: AsyncMock object has no attribute 'X'"
**Cause**: Mock not properly configured  
**Fix**: Use `Mock(spec=ClassName)` to ensure proper interface

## Related Documentation

- Design document: `george-scratch/AGENT_SELF_DIRECTION_DESIGN.md`
- Unit tests: `tests/unit/test_orchestrator.py`
- Intent detector: `src/logai/core/intent_detector.py`
- Orchestrator: `src/logai/core/orchestrator.py`
