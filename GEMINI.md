# Project Moirai: GenAI Press Review Service

## Project Overview

This project, codenamed "Moirai," is a GenAI-powered press review service. It is designed to aggregate news articles from various RSS feeds, process them using Large Language Models (LLMs), and identify significant events and correlations.
This is a public repository hosted on GitHub.

The architecture consists of:
-   **Backend:** A Python application built with the Flask web framework. It serves a RESTful API for accessing feeds, articles, and events.
-   **Frontend:** A modern web interface built with Vue.js and TypeScript.
-   **Data Storage:** Apache CouchDB is used as the primary database for storing feeds, articles, and processed event data.
-   **AI/ML:** The system is designed to integrate with LLMs for natural language processing tasks. It supports local models via Ollama and can be configured to use external services like Open-WebUI.
-   **Task Scheduling:** A background scheduler written in Python periodically fetches new articles from RSS feeds and triggers the analysis pipeline.
-   **Deployment:** The entire application is containerized using Docker and can be deployed to a Kubernetes cluster using the provided Helm chart.

## Key Technologies

-   **Backend:** Python, Flask, NLTK, scikit-learn
-   **Frontend:** Vue.js, TypeScript, Vite
-   **Database:** CouchDB
-   **Containerization:** Docker
-   **Orchestration:** Kubernetes, Helm

## How to Build and Run

### Running the Backend

1.  **Create a virtual environment:**
    ```bash
    python3 -m venv venv
    ```

2.  **Activate the virtual environment:**
    ```bash
    source venv/bin/activate
    ```

3.  **Install Python dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Start the backend server:**
    ```bash
    python3 main.py
    ```
    The backend will start on port `8088` by default.

### Running the Frontend (for development)

1.  **Navigate to the `ui` directory:**
    ```bash
    cd ui
    ```

2.  **Install frontend dependencies using Yarn:**
    ```bash
    yarnpkg install
    ```

3.  **Start the development server:**
    ```bash
    yarnpkg dev
    ```

4.  **Build for production:**
    ```bash
    yarnpkg build
    ```
    The production-ready files will be placed in the `ui/dist` directory and are automatically served by the Python backend.

## Development Conventions

-   The backend API endpoints are defined in `api/routes.py`.
-   Background processing tasks are located in the `tasks/` directory. `tasks/scheduler.py` orchestrates the execution of these tasks.
-   The frontend source code is in the `ui/src/` directory, with `App.vue` and `main.ts` as the main entry points.
-   The application is configured to run inside a Docker container. The `Dockerfile` uses a multi-stage build to first build the frontend and then combine it with the Python backend.
-   For Kubernetes deployments, the Helm chart is located in the `helm/` directory. It includes a dependency on the official CouchDB Helm chart.
-   Unit and integration tests can be found in files like `test_ollama.py`.
