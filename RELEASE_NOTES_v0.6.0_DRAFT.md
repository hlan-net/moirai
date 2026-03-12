# Moirai v0.6.0 (Draft)

Release date: TBD

## Highlights

- Adds end-to-end userspace isolation for agents across MCP, API, and UI.
- Improves chat export observability and provider robustness, including persisted resumed-session errors.
- Enhances local article search in the UI by augmenting results with database-backed matches.
- Adds contextual chat from article/issue/feed cards with persisted entity context.
- Improves reliability in CI and test execution, including integration environment alignment and async fixture stability.

## What Changed Since v0.5.2

### Agents and Userspace Isolation

- Enforced userspace-scoped agent configurations and execution.
- Added userspace-scoped agent API and UI wiring.
- Reduced duplication in agent route guard logic and refined migration/payload handling.
- Fixed list-config mock behavior for agent tests.

### Chat and Search

- Added verbose chat export tracing and persisted resumed-session errors.
- Improved chat export observability and provider handling.
- Improved tool trace argument visibility in chat flows.
- Preserved longevity selector shape for issue aliases in search.
- Fixed multi-word search term splitting to improve query matching.
- Fixed article search result description fallback (`description` -> `summary`) and included language metadata.

### Contextual Chat and Workflow

- Added contextual chat from article, issue, and feed cards with persisted context.
- Added side-drawer contextual chat modal with quick actions (raise issue/refine issue/feed recap).
- Added context badges in chat history sessions.

### Stability, CI, and Validation

- Addressed security review feedback.
- Reduced warning noise and Pydantic deprecations in CI.
- Fixed integration test credential alignment and environment collisions.
- Fixed async MCP test fixture behavior.
- Refactored URL validation helpers to reduce duplication and remove hardcoded protocol literals.
- Added centralized logic module allowlist validation in write paths.
- Strengthened schedule validation and cross-field checks.
- Added conflict-safe CouchDB update helper with retry on `_rev` conflicts.
- Added route-level `/api/agents` CRUD test coverage and userspace/ownership checks.

### Dependency Updates

- Bumped `minimatch` from `9.0.6` to `9.0.9`.
- Bumped `marked` from `17.0.3` to `17.0.4`.
- Updated UI dev dependencies.
- Updated docker-related GitHub Actions dependencies.

## Pull Requests Included

- #90: userspace isolation for agents (feature/agents-userspace-isolation)
- #89: chat export verbosity and robustness (feat/chat-export-verbose)
- #88: warning and validation cleanup (chore/warning-cleanup)
- #87, #86, #85, #83: dependency maintenance via Dependabot
- #91: route-level agent CRUD tests
- #92: logic module allowlist centralization
- #93: conflict-safe CouchDB updates
- #94: schedule validation hardening
- #95: multi-word search term splitting fix
- #96: contextual chat modal + persisted context

## Notes

- No breaking API changes are expected.
- Version fields were bumped to `0.6.0`; tag and GitHub release creation are the remaining release steps.
