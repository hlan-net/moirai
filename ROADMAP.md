# Moirai Project Roadmap

This document outlines the planned improvements and strategic direction for the Moirai project. For detailed technical designs, concepts, and user stories, refer to the individual documents in the [`docs/`](docs/) directory.

---

## 🗺️ High-Level Vision
Moirai is evolving from a data collection tool into a sophisticated, agent-driven synthesis engine. Our roadmap focuses on three pillars:
1. **User Empowerment:** Providing better interfaces for human-agent collaboration.
2. **Agentic Excellence:** Making our MCP-powered agents smarter, more reliable, and more observable.
3. **Platform Maturity:** Hardening security, performance, and multi-tenant capabilities.

---

## 🚀 Future Releases

### v0.9.0: Enhanced Synthesis & Social Integration
**Focus:** Streamlining the path from discovery to public dissemination.
- **[Social Export (Bluesky)](docs/social-export-bluesky.md):** Implementation of AT Protocol integration for sharing findings.
- **[Form-Based Issue Wizard](docs/proposal-form-wizard.md):** A traditional UI alternative for structured data entry.
- **[Issue Raise Wizard Refinement](docs/issue-raise-wizard.md):** Improved guidance for LLM-driven synthesis.

### v1.0.0: Agent Autonomy & Production Readiness
**Focus:** Reliability at scale and advanced agent capabilities.
- **[Agentic Infrastructure](docs/agentic-improvements.md):** Implementing Plan-Execute-Reflect loops and persistent agent memory.
- **[Security Hardening](docs/security-enhancements.md):** Transitioning to JWT sessions, Role-Based Access Control (RBAC), and server-side userspace isolation.
- **[Observability Suite](docs/agentic-improvements.md):** Deep tracing and intervention controls for production environments.

---

## 🛡️ Strategic Pillars

### Input Diversity & Precision
- **[Pointer Interaction Support](docs/pointer-interaction-wacom-touch.md):** Ensuring a fluid experience for Wacom, touch, and mouse users across the interactive dashboard.

### UI/UX Evolution
- **[Dashboard Overhaul](docs/dashboard-ux.md):** Reimagining the interface for higher data density and improved workflow efficiency.
- **[Deployment UX](docs/deploy-ux-improvements.md):** Simplifying the operational overhead of running Moirai in varied environments.

### Architectural Foundations
- **[MCP Tool Standardization](docs/mcp-tool-migration.md):** Moving towards a unified, versioned tool contract for all agents.
- **[Configuration Management](docs/settings-store-refactoring.md):** Centralizing application settings for better maintainability.

---

## 📚 Reference Documentation
- **[Architecture Overview](docs/architecture.md):** The high-level system design.
- **[External API Guide](docs/external-api.md):** How to integrate with Moirai from outside.
- **[Tutorials](docs/readme.md):** User, Admin, and Developer guides.
- **[Releasing Process](docs/releasing.md):** Standard procedure for project releases.
