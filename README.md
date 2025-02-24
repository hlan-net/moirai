# Morai - GenAI Press Review Service (Work in Progress)

Morai is a GenAI-powered press review service that aggregates and processes RSS feeds using AI models. It supports both local (Ollama) and external (Open-WebUI) models via configurable endpoints.

**Note:** This implementation is under active development and does not yet include all aspects of a Minimum Viable Product (MVP).

## Project Overview

Morai is built with:
- **Frontend:** Typescript Vue
- **Backend:** Python
- **Deployment:** A single container image running in Kubernetes as a Helm Chart
- **Supplementary Services:** CouchDB for data persistence, Open-WebUI, and Ollama for AI model processing

## Project Structure
```
.
├── api              # RESTful API handlers
├── tasks            # Scheduled tasks handlers
├── Dockerfile       # Docker file for container image
├── feeds            # Example feeds for testing 
├── helm             # Helm chart for deployment
├── main.py          # Main Python for Backend 
├── README.md        # This document
├── requirements.txt # Python dependencies
└── ui               # Vue frontend in Typescript
```

## Setup Instructions

1. **Clone the repository:**
   ```bash
   git clone https://github.com/hlan-net/moirai.git 
   cd morai

2. **Setup Python:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
	pip install -r requirements.txt

3. **Setup Vue:**
   ```bash
   cd ui
   yarn

4. **Run locally:**
   ```bash
   cd ui
   yarn build
   cd ..
   source venv/bin/activate
   python3 main.py

## Contributing

Contributions are welcome! Please feel free to submit a pull request or open an issue for any enhancements or bug fixes.

## License

This project is licensed under the MIT License. See the LICENSE file for more details.