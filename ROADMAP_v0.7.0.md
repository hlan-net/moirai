# Moirai v0.7.0 Implementation Roadmap

**Target Release:** Q2 2026 (April-June)
**Focus:** Issue Management & Social Export
**Status:** Planning phase

---

## 🚨 Immediate Actions (Blocking Current Release)

### 1. FIX: Raise Issue Wizard - Missing `premises` Parameter

**Status:** 🔴 CRITICAL BUG (v0.6.0 feature broken)
**Issue:** Chat wizard cannot create issues due to missing MCP tool parameter
**File:** `BUG_RAISE_ISSUE_WIZARD.md` (detailed analysis)
**Effort:** 2 hours
**Blocker:** Yes - users cannot use "Raise Issue" feature

**Quick Fix:**
- Update chat agent prompt to use `add_event` MCP tool instead of `forge_issue`
- Ensure article context is passed to agent
- Add integration test for end-to-end workflow

**Owner:** TBD
**Priority:** 🔴 P0 (Critical)

---

## 📋 v0.7.0 Features

### Feature 1: Traditional Form-Based Issue Wizard

**Status:** 🔴 Not started (design ready in `docs/PROPOSAL_FORM_WIZARD.md`)
**Effort:** 14 hours
**Sprint:** Week 1-3 of v0.7.0

#### Details:
- **What:** Multi-step form alternative to chat wizard
- **Why:** Better UX for traditional users, accessibility, discoverability
- **Who:** UI developer
- **Timeline:** 3 weeks

#### Deliverables:
- [x] Design mockups (in proposal doc)
- [x] Component structure planned
- [ ] IssueWizard.vue main component
- [ ] Step 1-4 sub-components
- [ ] Pinia state management store
- [ ] API integration
- [ ] Styling & animations
- [ ] Accessibility (WCAG AA)
- [ ] Unit & E2E tests

#### Success Criteria:
- Users can create issue in <2 minutes via form
- All 4 steps work without errors
- Form validates required fields
- Progress bar shows step position
- Preview step allows editing previous steps
- Hybrid approach: users choose chat vs form on first use

**Owner:** TBD

---

### Feature 2: Bluesky Post Generation from Issues

**Status:** 🔴 Not started (detailed design in `TODO_v0.7.0_ROADMAP.md`)
**Effort:** 50 hours (3 phases)
**Sprint:** Week 4-12 of v0.7.0

#### Phase 1: Core (22 hours)
- [x] Architecture designed
- [x] Code examples written
- [ ] MCP tool for Bluesky API (atproto SDK)
- [ ] Agent logic for post generation (LLM-powered)
- [ ] UI: Share button on issue detail
- [ ] Encrypted credential storage
- [ ] Auto-threading for long posts
- [ ] Tests

**Timeline:** 3-4 sprints

#### Phase 2: Analytics (12 hours)
- Track engagement metrics
- Link to issues
- Display in UI

#### Phase 3: Automation (16 hours)
- SCHEDULED agent for daily digests
- AI selects best issues
- Customizable templates

**Success Criteria:**
- Share issue to Bluesky in 1 click
- Posts include issue context & attribution link
- No credential leaks
- Thread support for long posts

**Owner:** TBD

---

## 📊 Feature Comparison: v0.6.0 vs v0.7.0

| Feature | v0.6.0 | v0.7.0 |
|---------|--------|--------|
| Chat wizard for issues | ✅ (broken in v0.6.0) | ✅ Fixed |
| Form wizard for issues | ❌ | ✅ New |
| Issue raising | ✅ (after fix) | ✅ 2 methods |
| Share to Bluesky | ❌ | ✅ Phase 1 |
| Post analytics | ❌ | ✅ Phase 2 |
| Auto-posting | ❌ | ✅ Phase 3 |
| Issue lifespan tracking | ✅ | ✅ |
| Issue sealing | ✅ | ✅ |
| Customizable agents | ✅ | ✅ |

---

## 🗓️ Sprint Plan

### Sprint 1 (Week 1-2): Bug Fix + Form Wizard Setup
- **Monday:** Fix raise issue wizard bug (critical path)
- **Tuesday-Wednesday:** Implement form wizard components
- **Thursday-Friday:** State management & routing

### Sprint 2 (Week 3-4): Form Wizard Polish + Bluesky Start
- **Monday-Wednesday:** Form wizard testing, styling, accessibility
- **Thursday-Friday:** Start Bluesky integration (MCP tool setup)

### Sprint 3-4 (Week 5-8): Bluesky Phase 1
- Bluesky API client
- Post generation logic
- UI button integration
- Testing & security

### Sprint 5-6 (Week 9-12): Bluesky Phase 2-3 (Optional for v0.7.0)
- Analytics
- Automation agents
- Templates

---

## 📌 Dependencies

### External
- `atproto` Python package (for Bluesky) — v0.0.58+
- `cryptography` (for credential encryption) — v41.0.0+

### Internal
- MCP tool system (already in place)
- Agent orchestrator (changes feed pattern, v0.6.0)
- LLM integration (for post generation)

### Blockers
- None identified (all prerequisites exist)

---

## 🎯 Success Metrics

### For Bug Fix
- [x] Issue wizard creates issues without errors
- [x] Integration test passes
- [x] User can complete wizard end-to-end

### For Form Wizard
- [x] Form loads without errors
- [x] All 4 steps navigable
- [x] Form submission creates issue
- [x] Accessibility audit passes
- [x] Mobile responsive design verified

### For Bluesky
- [x] Post successfully created on Bluesky
- [x] Post includes issue context
- [x] Credentials encrypted (no plaintext in DB)
- [x] Audit log tracks all posts
- [x] Rate limiting prevents spam

---

## 🔄 Rollout Plan

### Phase 1: Bug Fix (Hotfix, immediate)
- Release as v0.6.1 patch
- Unblocks issue creation

### Phase 2: Form Wizard (v0.7.0 RC1)
- Hybrid approach: both chat and form available
- User preference saved in localStorage
- Beta feedback period: 1 week

### Phase 3: Bluesky (v0.7.0)
- Phase 1 (core) required for release
- Phase 2-3 optional (can defer to v0.7.1)

---

## 📝 Documentation

To be created during implementation:

- [ ] Form Wizard user guide (tutorials/TUTORIAL_USER.md update)
- [ ] Bluesky setup guide (new doc)
- [ ] API changes (if any new endpoints)
- [ ] Admin guide for managing Bluesky credentials
- [ ] Developer guide for extending social export (multi-platform)

---

## 🧪 Testing Strategy

### Unit Tests
- Form validation (required fields, formats)
- State management (Pinia store)
- Agent logic (post generation, threading)

### Integration Tests
- Form submission → Issue creation → UI display
- Bluesky API → Post creation → Audit log
- Error handling for failed posts

### E2E Tests (Playwright)
- User completes form → Issue appears in list
- User shares issue → Confirmation + Bluesky link
- User views analytics → Engagement metrics shown

### Manual Testing Checklist
- [ ] Mobile form on iPhone 12
- [ ] Form on Firefox (accessibility)
- [ ] Very long issue titles (threading)
- [ ] Multiple articles selected
- [ ] Network failure scenarios

---

## 💰 Resource Allocation

| Role | Hours | Weeks |
|------|-------|-------|
| Frontend dev (form) | 14 | 2-3 |
| Backend dev (Bluesky) | 22 | 3-4 |
| QA/Testing | 10 | 2 |
| Docs | 4 | 1 |
| **Total** | 50 | 8 |

**Team:** 2 FTE (1 frontend, 1 backend)
**Duration:** 8 weeks (2 months)

---

## 🚀 Go/No-Go Criteria

### Must Have (Go/No-Go for v0.7.0)
- ✅ Bug fix deployed & tested
- ✅ Form wizard fully functional
- ✅ Bluesky Phase 1 complete
- ✅ Security audit passed
- ✅ All unit tests pass
- ✅ Documentation complete

### Nice to Have (Can defer to v0.7.1)
- Bluesky Phase 2 (Analytics)
- Bluesky Phase 3 (Automation)
- Multi-platform support

---

## 📞 Decision Needed

**From stakeholders:**

1. **Should Bluesky Phase 2-3 be in v0.7.0 or v0.7.1?**
   - Proposal: v0.7.0 has Phase 1 only; defer analytics & automation
   - Reasoning: Tighter timeline, reduce risk

2. **Should form wizard be default or chat wizard?**
   - Proposal: User chooses on first use, remember preference
   - Reasoning: Serves both audiences, no disruption

3. **Do we need A/B testing for form vs chat?**
   - Proposal: Yes, if resources available (optional)
   - Reasoning: Data-driven decision for future improvements

---

## 🔗 Related Documents

- `docs/PROPOSAL_FORM_WIZARD.md` — Form wizard detailed design
- `TODO_v0.7.0_ROADMAP.md` — Bluesky detailed roadmap
- `BUG_RAISE_ISSUE_WIZARD.md` — Bug fix analysis & solution
- `CLAUDE.md` — Architecture & conventions
- `CHANGELOG.md` — Version history

---

## 👥 Next Steps

1. **Assign Owner** for bug fix (immediate)
2. **Assign Owner** for form wizard (Week 1)
3. **Assign Owner** for Bluesky (Week 4)
4. **Schedule kickoff** meeting with team
5. **Review roadmap** with stakeholders
6. **Get feedback** on phasing & priorities

---

**Last Updated:** 2026-03-13
**Status:** Ready for review
**Approvals Needed:** Product, Engineering, Security
