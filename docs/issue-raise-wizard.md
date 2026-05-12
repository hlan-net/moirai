# Issue Raise Wizard: Context-Aware Synthesis

## Overview
The "Raise Issue" wizard is a core component of Moirai's synthesis pipeline. it provides a guided experience for users to transform raw data (articles) into structured observations (Issues/Events). 

By combining human guidance with LLM synthesis via MCP tools, the wizard ensures that every created issue is contextually rich and properly linked to its premises.

## Conceptual Design
The wizard operates on the principle of **Assisted Synthesis**. Instead of requiring a user to manually fill out complex data structures, the wizard uses a chat-based interface to:
1. **Gather Intent:** Ask clarifying questions about the significance of the data.
2. **Contextualize:** Provide the LLM agent with the relevant background (articles, summaries, IDs).
3. **Execute:** Leverage specialized MCP tools to forge the issue with the correct structure.

## Technical Workflow

### 1. Intent Gathering (UI)
The frontend wizard (`ContextChatModal.vue`) leads the user through a set of targeted questions. This phase focuses on the "why" and "so what" of the article being analyzed.

### 2. Context Injection (API)
When the user submits their answers, the backend (`chat_routes.py`) constructs a rich context preamble. This preamble includes:
- **Article Metadata:** Title, summary, and internal GUID.
- **Guidance:** Specific instructions for the agent on which MCP tools to use (e.g., preferring `add_event` for article-based issues).

### 3. Agentic Synthesis (MCP)
The agent processes the user's intent and the injected context. It then calls the `add_event` tool, which acts as a high-level abstraction over the base `forge_issue` tool. 

This abstraction automatically:
- Formats the article link into a valid `premise` object.
- Assigns the appropriate `longevity` (e.g., `transient`).
- Validates the userspace isolation.

## Implementation Principles

### Tool Abstraction
To ensure reliability, we use simplified tool aliases like `add_event` for agents. This reduces the complexity of the parameters the agent must generate (e.g., complex lists of dictionaries) and shifts that responsibility to the tool implementation.

### Explicit Guidance
The system message for the chat agent is dynamically updated based on the context. If an article is present, the agent is explicitly told how to handle it, reducing "hallucinations" in tool selection.

## Future Enhancements
- **Hybrid Support:** Integrating the [Form-Based Wizard](PROPOSAL_FORM_WIZARD.md) as an alternative for power users.
- **Multi-Source Synthesis:** Expanding the wizard to allow raising issues from multiple articles simultaneously.
- **Feedback Loops:** Allowing the agent to suggest refinements to the issue title or description based on the user's initial answers.
