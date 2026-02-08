# LLM Configuration Guide

Moirai supports multiple LLM providers to power its agentic capabilities. You can configure these settings directly from the web interface.

## Accessing Configuration

1. Open the Moirai UI (default: [http://localhost:8088](http://localhost:8088)).
2. Navigate to the **Settings** page via the sidebar or top navigation.
3. Scroll to the **LLM Endpoint Configuration** section.

## Supported Providers

### 1. Ollama (Default)

Ideal for running local models without external API costs.

- **Endpoint URL:** Defaults to `http://host.docker.internal:11434/v1`.
  - *Note: If running Moirai in Docker, `host.docker.internal` allows it to access Ollama running on your host machine.*
- **Model Name:** Select a model installed on your Ollama instance (e.g., `llama3`, `gemma`).
  - If the dropdown is empty, ensure your Ollama instance is running and reachable.

### 2. OpenAI

Use powerful cloud models like GPT-4.

- **API Key:** Enter your OpenAI API Key (starts with `sk-...`).
- **Model Name:** Click **Fetch Models** to load available models associated with your key, or manually enter a model name (e.g., `gpt-4-turbo`, `gpt-3.5-turbo`).

### 3. Google Gemini

Use Google's Gemini models.

- **API Key:** Enter your Google Gemini API Key.
- **Model Name:** Click **Fetch Models** to see available models, or manually enter one (e.g., `gemini-1.5-pro`, `gemini-1.5-flash`).

## Switching Providers

To switch between providers:

1. Select the desired provider radio button (Ollama, OpenAI, or Gemini).
2. Ensure the configuration for that provider is correct.
3. Click **Save All Settings** at the bottom of the page.
4. Navigate back to the **Chat** page to start using the new model.

## Troubleshooting

- **"Fetch Models" fails:**
  - Check if the API Key is correct.
  - Check internet connectivity from the Moirai container.
  - For Ollama, ensure CORS is configured if running on a different origin, or that the container can reach the host.
- **Chat errors:**
  - Check the container logs (`docker compose logs -f api`) for detailed error messages.
  - Verify that the selected model actually supports chat completion / tool calling.
