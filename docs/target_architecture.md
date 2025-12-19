# Target Architecture Description

## 1. Project Goal

The project's goal is to create a press review service that decouples the core application from the AI/ML models. The application will be responsible for aggregating RSS feeds, storing articles, and providing a user interface for reviewing articles, events, and trends. The AI/ML processing will be performed by external services that interact with the application through a set of "Model Context Protocol" (MCP) services.

## 2. System Components

The target architecture consists of the following components:

-   **Frontend:** A Vue.js single-page application that provides the user interface for reviewing articles, events, and trends.
-   **Backend:** A Python/Flask application that provides the following services:
    -   RSS feed aggregation.
    -   A web server for the frontend.
    -   A set of RESTful APIs for the frontend to consume.
    -   The "Model Context Protocol" (MCP) services for external AI/ML services.
-   **Database:** A CouchDB database for storing articles, events, and trends.
-   **External AI/ML Services:** External services that are responsible for analyzing articles, identifying events, and creating trends. These services will use the MCP services to interact with the application's data.

## 3. Data Flow

1.  The backend's scheduler periodically fetches new articles from RSS feeds and stores them in the CouchDB database.
2.  The frontend displays the articles in a chronological list.
3.  External AI/ML services use the "Retrieve Articles" MCP service to get the latest articles for processing.
4.  After processing the articles, the external AI/ML services use the "Write Events" MCP service to create new events and link them to the relevant articles.
5.  The external AI/ML services can also use the "Create Trends" MCP service to create new trends and link events to them.
6.  The frontend displays the events and trends in their respective columns, with links to the associated articles and events.

## 4. Model Context Protocol (MCP) Services

The MCP services are a set of RESTful APIs that allow external AI/ML services to interact with the application's data. The following MCP services will be implemented:

-   **Retrieve Articles Service:**
    -   `GET /mcp/articles`: Retrieves a list of articles, with optional filtering by date or status.
-   **Write Events Service:**
    -   `POST /mcp/events`: Creates a new event and links it to one or more articles.
-   **Read/Search Events Service:**
    -   `GET /mcp/events`: Retrieves a list of events.
    -   `GET /mcp/events/<event_id>`: Retrieves a single event, with an option to include the linked articles.
-   **Create Trends Service:**
    -   `POST /mcp/trends`: Creates a new trend and links it to one or more events.
-   **Read Trends Service:**
    -   `GET /mcp/trends`: Retrieves a list of trends.
    -   `GET /mcp/trends/<trend_id>`: Retrieves a single trend, with options to include linked events and articles.
