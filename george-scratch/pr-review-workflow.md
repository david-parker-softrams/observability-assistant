# Pull Request Review Workflow

## Overview
This document describes the two-tier PR review process for the observability-assistant project:
1. **Automated review** by GitHub Copilot (quick checks)
2. **Manual review** by Han-Ron code-reviewer agent (deep project-specific review)

---

## Automated Reviews: GitHub Copilot

### What It Does
GitHub Copilot automatically reviews every PR for:
- Security vulnerabilities
- Common bugs and logic errors
- Code style and best practices
- Performance issues

### Setup
See `george-scratch/github-copilot-review-setup.md` for instructions on enabling Copilot reviews.

### When It Runs
- Automatically when PR is opened
- Automatically when new commits are pushed to PR
- Reviews appear from "GitHub Copilot" user
- Takes 30-90 seconds per review

### Output
- Line-specific comments in "Files changed" tab
- General feedback summary
- Can request changes or approve

---

## Manual Reviews: Han-Ron (George's Code-Reviewer Agent)

### What It Does
Han-Ron provides deeper, project-specific code review focusing on:
- **Architecture & Design Patterns** - Does this fit our overall design?
- **LogAI-Specific Concerns** - Textual UI patterns, AWS integration, async usage
- **Maintainability** - Will this be easy to understand and modify later?
- **Testing Strategy** - Are we testing the right things the right way?
- **Team Standards** - Does this follow our conventions and workflows?

### When To Request Han-Ron Review

Request Han-Ron review for:
- ✅ **Large features** (200+ lines changed)
- ✅ **Architecture changes** (new patterns, refactoring)
- ✅ **Complex logic** (algorithms, state management)
- ✅ **New integrations** (AWS, third-party libraries)
- ✅ **Security-sensitive code** (authentication, data handling)
- ✅ **When Copilot raises concerns** and you want deeper analysis

You can skip Han-Ron review for:
- ⏭️ **Trivial changes** (typo fixes, formatting)
- ⏭️ **Documentation only** (unless major docs overhaul)
- ⏭️ **Dependency updates** (unless breaking changes)
- ⏭️ **When Copilot approved** and changes are straightforward

### How To Request Han-Ron Review

#### Method 1: Via George (TPM)
Simply ask George in conversation:
```
"Hey George, can you have Han-Ron review PR #123?"
```

George will:
1. Fetch the PR details and diff
2. Task Han-Ron with reviewing the code
3. Post Han-Ron's review findings back to you
4. You can ask follow-up questions about the review

#### Method 2: Direct Request (If George Is Unavailable)
If you're working without George active:
1. Post a comment on the PR: "Request review by Han-Ron"
2. When you next talk to George, he'll see pending reviews
3. George will coordinate Han-Ron's review and post results

### What Han-Ron Reviews

Han-Ron receives:
- Full PR diff
- PR title and description
- List of files changed
- Commit messages
- Project context (codebase understanding)

Han-Ron provides:
- **Summary** - What the PR does and overall assessment
- **Strengths** - What's done well
- **Concerns** - Issues that should be addressed
- **Suggestions** - Optional improvements
- **Questions** - Things that need clarification
- **Verdict** - APPROVE / REQUEST_CHANGES / COMMENT

### Review Timeline

- **Copilot**: 30-90 seconds (automatic)
- **Han-Ron**: 2-10 minutes (manual request, depends on PR size and George's availability)

---

## Complete PR Review Workflow

### 1. Create PR
```bash
git push -u origin feature/my-feature
gh pr create --title "Feature: My Feature" --body "Description..."
```

### 2. Copilot Review (Automatic)
- Wait 1-2 minutes for Copilot to post review
- Address any issues Copilot identifies
- Push fixes if needed (Copilot re-reviews automatically)

### 3. Han-Ron Review (Manual - If Needed)
**When to request**: See "When To Request Han-Ron Review" section above

**How to request**:
- Talk to George: "Have Han-Ron review PR #123"
- Wait for Han-Ron's detailed review (2-10 minutes)
- Review Han-Ron's feedback
- Ask George follow-up questions if needed
- Address concerns and push updates

### 4. Merge
Once both reviews are satisfied:
```bash
# Option 1: Merge via UI
# GitHub → PR → Merge button

# Option 2: Merge via CLI
gh pr merge <PR#> --squash

# Option 3: Ask George
"George, please merge PR #123"
```

---

## Example: Requesting Han-Ron Review

### Small Documentation PR (Skip Han-Ron)
```
You: "George, I have PR #45 ready - just fixing typos in README"
George: "Great! Since it's just docs, Copilot's review should be sufficient.
         Let me know when Copilot approves and I'll merge it."
```

### Large Feature PR (Request Han-Ron)
```
You: "George, PR #46 is ready - I added a new log export feature (350 lines).
      Can Han-Ron review it?"
George: "Absolutely! Let me have Han-Ron take a look at the export feature."
[Han-Ron reviews...]
George: "Han-Ron reviewed PR #46. He likes the overall approach but has
         concerns about error handling in the export_logs() function.
         He's asking if we handle AWS rate limiting. Want me to share
         his full review?"
You: "Yes please, and ask him specifically about the rate limiting concern"
[Discussion continues...]
```

---

## Tips for Better Reviews

### For Copilot
- Write clear PR descriptions (Copilot reads them)
- Use descriptive commit messages
- Keep PRs focused (single feature/fix)
- Add comments for complex logic

### For Han-Ron
- Provide context in PR description
  - Why is this change needed?
  - What alternatives were considered?
  - Any concerns or questions you have?
- Link to related issues or design docs
- Call out specific areas you want feedback on
- Mention if you tried something new or experimental

### For Both
- Keep PRs reasonably sized (< 500 lines when possible)
- Split large changes into multiple PRs
- Add tests before requesting review
- Run pre-commit hooks before pushing

---

## Benefits of Two-Tier Review

| Benefit | Description |
|---------|-------------|
| **Speed** | Copilot provides immediate feedback |
| **Depth** | Han-Ron provides thoughtful project-specific review |
| **Coverage** | Copilot catches common issues, Han-Ron catches design issues |
| **Learning** | Han-Ron explains reasoning, helps improve skills |
| **Flexibility** | Skip Han-Ron for trivial changes, use for complex ones |
| **Cost** | Copilot included, Han-Ron only when needed |

---

## Frequently Asked Questions

### Q: Do I need both reviews for every PR?
**A:** No. Copilot reviews every PR automatically. Han-Ron review is optional and recommended for complex/large changes.

### Q: What if Copilot and Han-Ron disagree?
**A:** Bring it up with George. Han-Ron has project context that Copilot doesn't, but Copilot may catch things Han-Ron missed. George will help resolve.

### Q: Can Han-Ron review a PR after it's merged?
**A:** Yes! If you want a post-merge review for learning purposes, just ask George.

### Q: How do I know if a PR needs Han-Ron review?
**A:** If you're asking yourself "I wonder if this is the best approach?" - that's when to request Han-Ron.

### Q: Can I request Han-Ron review before opening the PR?
**A:** Yes! Show George your changes and ask "Should I PR this?" before creating the PR. He can have Han-Ron do a pre-review.

### Q: What if Han-Ron requests changes?
**A:** Address the concerns, push updates, then ask George "Can Han-Ron take another look at PR #X?" for a follow-up review.

---

**Next Steps**: See `george-scratch/github-copilot-review-setup.md` to enable Copilot reviews.
