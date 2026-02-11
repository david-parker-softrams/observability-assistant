# Feature Request: AWS Profile Command-Line Argument

**Date:** February 11, 2026  
**Requested by:** User  
**Priority:** High  
**Status:** Ready for Implementation

---

## Overview

Add a command-line argument `--aws-profile` to allow users to specify which AWS profile to use when connecting to CloudWatch, overriding the environment variable `AWS_PROFILE`.

## Motivation

Users often work with multiple AWS accounts or roles and need to quickly switch between them without modifying environment variables or `.env` files. This is a common workflow for:

- DevOps engineers managing multiple environments (dev, staging, prod)
- SREs working across different AWS accounts
- Consultants supporting multiple clients
- Testing and validation across different AWS roles

## Current Behavior

Currently, AWS profile selection works via environment variables:
1. `AWS_PROFILE` in `.env` or shell environment (highest priority)
2. `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` (fallback)
3. Default boto3 credential chain (fallback)

To switch profiles, users must either:
- Modify `.env` file
- Set environment variable: `AWS_PROFILE=profile-name logai`

## Proposed Behavior

Add a command-line argument that takes precedence over environment variables:

```bash
# Use specific profile via command line
logai --aws-profile bosc-dev

# Environment variable still works as fallback
AWS_PROFILE=bosc-dev logai

# .env file still works as fallback
logai
```

### Precedence Order (highest to lowest):
1. **Command-line argument** `--aws-profile` (NEW - highest priority)
2. Environment variable `AWS_PROFILE`
3. Explicit credentials (`AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`)
4. Default boto3 credential chain

## Technical Requirements

### 1. CLI Argument Definition

Add to `src/logai/cli.py`:
```python
parser.add_argument(
    "--aws-profile",
    type=str,
    help="AWS profile name to use for CloudWatch access",
    default=None,
    metavar="PROFILE",
)
```

### 2. Settings Override

The Settings class needs to accept runtime overrides for `aws_profile`:
- Either pass through constructor
- Or add a method to override specific settings

### 3. Configuration Flow

```
CLI argument --aws-profile
    ↓
Override settings.aws_profile if provided
    ↓
Pass settings to CloudWatchDataSource
    ↓
CloudWatchDataSource uses profile (existing logic already handles this)
```

### 4. Help Text Updates

Update the CLI help text in `cli.py` to document the new argument:
```
Examples:
  logai                              # Start with default profile
  logai --aws-profile my-profile     # Use specific AWS profile
  logai --version                    # Show version information
```

Update environment variables section:
```
Environment Variables:
  AWS_PROFILE                     # AWS profile (can be overridden with --aws-profile)
  AWS_DEFAULT_REGION              # AWS region for CloudWatch
  ...
```

### 5. Startup Output

Update the configuration summary output to show which profile is being used:
```python
print(f"✓ AWS Region: {settings.aws_region}")
if settings.aws_profile:
    print(f"✓ AWS Profile: {settings.aws_profile}")
print(f"✓ PII Sanitization: ...")
```

## Implementation Notes

### Files to Modify

1. **`src/logai/cli.py`**
   - Add `--aws-profile` argument to parser
   - Override `settings.aws_profile` if argument provided
   - Update help text and examples
   - Update startup output

2. **`src/logai/config/settings.py`** (may need minor changes)
   - Ensure `aws_profile` can be overridden at runtime
   - May need to add a method like `override_aws_profile(profile: str)`

3. **`tests/unit/test_cli.py`** (if it exists, otherwise create)
   - Test that `--aws-profile` argument is parsed correctly
   - Test precedence: CLI arg > env var
   - Test startup output shows correct profile

### Existing Code That Already Handles This

The good news: `CloudWatchDataSource` already correctly handles profile-based authentication (fixed in commit 7224b63). Once we set `settings.aws_profile`, everything downstream just works!

## Testing Strategy

### Manual Testing
```bash
# Test 1: Default behavior (no change)
logai

# Test 2: Profile via command line
logai --aws-profile bosc-dev

# Test 3: Profile via command line overrides environment
AWS_PROFILE=wrong-profile logai --aws-profile bosc-dev

# Test 4: Help text shows new argument
logai --help
```

### Unit Tests
- Test argument parsing
- Test settings override logic
- Test precedence order

### Integration Tests
- Verify CloudWatch connection works with CLI-specified profile
- Verify tool calls succeed with correct profile

## Success Criteria

1. ✅ User can run `logai --aws-profile <name>` and connect to CloudWatch with that profile
2. ✅ CLI argument takes precedence over environment variables
3. ✅ Startup output shows which profile is being used
4. ✅ Help text documents the new argument with examples
5. ✅ All existing tests still pass
6. ✅ New tests validate the feature works correctly

## Open Questions

1. **Should we also add `--aws-region` for consistency?**
   - Probably yes, for symmetry
   - Would allow: `logai --aws-profile prod --aws-region us-west-2`

2. **Should we validate the profile exists before starting?**
   - boto3 will error on first API call if profile is invalid
   - Early validation would provide better UX
   - Could add a connection test during initialization

## Related Future Enhancements

- Interactive profile selection (list available profiles, let user choose)
- Profile-specific caching (separate cache per profile/region)
- Save last-used profile as default
- Support for multiple profiles in one session (switch without restart)

---

## Implementation Assignment

**Assigned to:** Jackie (software-engineer agent)  
**Estimated effort:** Small feature (1-2 hours)  
**Complexity:** Low - straightforward argument parsing and settings override

**Review by:** Billy (code-reviewer agent)  
**Testing by:** Raoul (qa-engineer agent) - write tests  
**Documentation by:** Tina (technical-writer agent) - update user docs

---

## References

- Current CLI implementation: `src/logai/cli.py`
- Settings implementation: `src/logai/config/settings.py`
- CloudWatch credential handling: `src/logai/providers/datasources/cloudwatch.py` (lines 51-79)
- Previous AWS profile fix: Commit 7224b63
