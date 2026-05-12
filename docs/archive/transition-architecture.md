# First Transition Architecture

## 1. Introduction

This document outlines the steps for the first transition from the current architecture to the target architecture, which decouples the AI/ML components from the core application. This transition will focus on removing the existing AI/ML logic, implementing the "Model Context Protocol" (MCP) services, and updating the UI to include a "Trends" column.

## 2. Transition Steps

### Step 1: Decouple AI/NLP Logic

The first step is to remove the existing AI/NLP logic from the application. This includes:

-   Removing the `transformers`, `nltk`, `sentence-transformers`, `numpy`, and `scikit-learn` dependencies from `requirements.txt`.
-   Removing the `article_processor.py` and `event_correlator.py` files from the `tasks` directory.
-   Updating the `tasks/scheduler.py` to remove the calls to the `ArticleProcessor` and `EventCorrelator`.
-   Removing the `test_ollama.py` file.

### Step 2: Implement Model Context Protocol (MCP) Services

The next step is to implement the MCP services as a new set of API endpoints in the backend. These endpoints will be used by external AI/ML services to interact with the application's data. A new API blueprint will be created for the MCP services.

-   Create a new file `api/mcp_routes.py`.
-   Implement the "Retrieve Articles" service endpoint.
-   Implement the "Write Events" service endpoint.
-   Implement the "Read/Search Events" service endpoints.
-   Implement the "Create Trends" service endpoint.
-   Implement the "Read Trends" service endpoints.
-   Register the new blueprint in `main.py` under the `/mcp` prefix.

### Step 3: Update the Database Schema

The database schema will need to be updated to include a new database for trends. The structure of the documents will be as follows:

-   **trends:**
    -   `_id`: Trend ID
    -   `name`: Trend name
    -   `description`: Trend description
    -   `event_ids`: A list of IDs of events linked to this trend.

### Step 4: Update the UI

The final step is to update the frontend to include a "Trends" column and to display the data from the new API endpoints.

-   Create a new `TrendColumn.vue` component.
-   Update `MainPage.vue` to include the `TrendColumn.vue` component.
-   Update the frontend to fetch and display trends from the `/api/trends` endpoint.
-   Update the `EventColumn.vue` to allow linking events to trends.

## 3. Outcome

After this transition, the application will no longer have any internal AI/ML processing capabilities. Instead, it will provide a set of APIs for external services to perform these tasks. The UI will be updated to reflect the new data model, including the addition of "Trends".
