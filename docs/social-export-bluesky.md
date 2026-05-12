# Social Export: Bluesky Integration

## Overview
Moirai aims to not only synthesize information but also to facilitate its dissemination. The Social Export functionality allows synthesized Issues and Trends to be shared directly to external social platforms, starting with **Bluesky**.

This document outlines the conceptual approach and architectural design for exporting Moirai data to the AT Protocol.

## Conceptual Framework
Social export is the final step in the "Information -> Action" pipeline. It bridges the gap between Moirai's internal data lake and the public discourse.

Key goals include:
1. **Context Preservation:** Ensuring that exported posts retain links to their original articles or Moirai issues.
2. **Seamless Workflow:** Allowing analysts to share findings with a single click from the dashboard.
3. **Agentic Automation:** Enabling LLM agents to draft and schedule social media digests based on synthesized trends.

## Technical Architecture

### 1. AT Protocol Integration
We utilize the `atproto` SDK to interact with the Bluesky API. The integration is encapsulated within a specialized MCP tool, allowing both human users and agents to trigger exports.

### 2. Post Generation Logic
Exporting an Issue involves more than just copying a title. Our agent-powered generation logic:
- Summarizes the core finding.
- Attributes the source articles.
- Handles threading for long-form analyses.
- Formats mentions and hashtags for optimal engagement.

### 3. Security & Credentials
External credentials (app passwords) are stored with encryption-at-rest. The export service operates on a principle of least privilege, only accessing the specific accounts authorized by the userspace.

## Functional Components

### The Share Interface
A "Share" button on the Issue and Trend detail views opens an export preview. Users can review the generated text, adjust threading, and confirm the post.

### Automated Digests
Agents can be configured to perform daily or weekly "Trend Digests," selecting the most significant observations from a userspace and presenting them as a cohesive thread.

## Future Multi-Platform Support
While Bluesky is the initial target due to its open nature (AT Protocol), the architecture is designed to be extensible to other platforms (e.g., Mastodon, LinkedIn) by implementing additional export adapters.
