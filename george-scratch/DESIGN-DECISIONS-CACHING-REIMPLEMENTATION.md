# Design Decisions Log - Caching Reimplementation

**Date:** Feb 23, 2026
**Project:** Caching System Reimplementation
**Decision Maker:** David Parker (User/Product Owner)
**Documented By:** George (TPM)

---

## Decision Summary

Based on Saanvi's comprehensive design document, the following decisions have been made:

### Decision 1: Fetch Limit - Increase to 5
**Saanvi's Question:** Keep at 3 or increase to 5?
**Decision:** **Increase to 5**
**Rationale:** More flexible for large datasets, gives agent more room to explore data before hitting limits

**Impact:**
- Update `max_auto_chunk_fetches` default from 3 to 5 in settings.py
- Update all documentation referencing the limit
- Update test expectations

### Decision 2: Cache Age for Follow-up Detection - Increase to 10 Minutes
**Saanvi's Question:** Keep 5 minutes or adjust?
**Decision:** **Increase to 10 minutes**
**Rationale:** Longer window accommodates slower users and agents, reduces risk of missing valid follow-up questions

**Impact:**
- Set FOLLOW_UP_CACHE_AGE_THRESHOLD to 10 minutes (600 seconds)
- Update documentation explaining the window
- Consider making this configurable in future (not now)

### Decision 3: Backward Compatibility - Clean Break
**Saanvi's Question:** Preserve old `to_context_dict()` method or clean break?
**Decision:** **Clean break - Remove old method**
**Rationale:** Simpler code, no confusion about which method to use, we're on a feature branch so we can test thoroughly

**Impact:**
- Remove or fully replace old `to_context_dict()` implementation
- Update all callers to use new structure
- Update all tests to expect new structure
- No backward compatibility shim needed

---

## Design Approval Status

✅ **APPROVED** - Saanvi's design document is approved for implementation

**Key Approved Elements:**
1. ✅ Result Delivery: Option A (Separate Message Timing)
2. ✅ Data Structure: 5 keys (down from 7)
3. ✅ Sample Selection: Diversity-aware algorithm
4. ✅ Statistics: Structured fields with confidence indicators
5. ✅ Fetch Limit: Per-cache-ID, per-turn tracking
6. ✅ Timeline: 2-3 days
7. ✅ Implementation plan: 3 phases

**Modified Parameters:**
- max_auto_chunk_fetches: 3 → **5**
- FOLLOW_UP_CACHE_AGE_THRESHOLD: 5 minutes → **10 minutes**
- Backward compatibility: Preserve flag → **Clean break**

---

## Next Steps

1. ✅ **Saanvi:** Design complete - Document delivered
2. 🔄 **Jackie:** Begin Phase 1 implementation (result delivery fix)
3. ⏳ **Raoul:** Standing by for testing phase
4. ⏳ **Han-Ron:** Standing by for code review
5. ⏳ **Tina:** Standing by for documentation updates

---

## Notes for Implementation Team

### For Jackie (Engineer):

**High Priority Guidance:**
- Follow Saanvi's design document closely: `george-scratch/DESIGN-CACHING-REIMPLEMENTATION.md`
- Use the three approved parameter values above
- Implement clean break (no backward compatibility code)
- Focus on Phase 1 first (result delivery), get that working before Phase 2
- Commit frequently with clear messages
- Run tests after each phase

**Timeline Expectation:**
- Phase 1: 4-6 hours (result delivery mechanism)
- Phase 2: 4-6 hours (known issues fixes)
- Phase 3: 4-6 hours (testing and validation)
- Total: 2-3 days

### For Raoul (QA):

**Test Priorities:**
1. Result visibility (agent can see and analyze results)
2. Follow-up detection (guidance injected at right time)
3. Fetch limit enforcement (stops at 5 fetches)
4. Sample event quality (diversity algorithm works)
5. Statistics accuracy (structured fields + confidence)
6. No regressions (all bug fixes still work)

### For Han-Ron (Code Reviewer):

**Review Focus:**
1. Code clarity and maintainability
2. Test coverage adequacy
3. No reintroduction of known bugs
4. Performance implications
5. Error handling robustness

---

**Document Status:** ✅ Final
**Approved By:** David Parker (Product Owner)
**Documented By:** George (TPM)
**Date:** Feb 23, 2026
