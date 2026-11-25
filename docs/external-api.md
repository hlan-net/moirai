# External REST API Documentation

## Note
This documentation describes the **REST API endpoints** served by the Flask backend (Port 8088) under the `/mcp` prefix.

**This is NOT the Model Context Protocol (MCP) Server.**
The actual MCP Server runs on Port 8090 via SSE (Server-Sent Events) and is designed for direct connection with MCP clients (like Claude Desktop or the Moirai Chat Agent).

These REST endpoints are provided for external non-MCP services or legacy integrations that need to access the data via standard HTTP methods.

## Introduction

The External API provides a set of RESTful endpoints...

## Authentication

Every `/mcp` endpoint requires credentials, as the `/api` endpoints do: a JWT in `Authorization: Bearer <token>` (from `POST /api/auth/login`) or HTTP Basic with the admin credentials. Requests without them get `401`. The Helm chart's nginx forwards only `/api` to the backend, so these endpoints are reachable only inside the cluster.

## Endpoints

### Articles

#### Retrieve Articles

-   **Method:** `GET`
-   **Path:** `/mcp/articles`
-   **Description:** Retrieves the newest articles, newest first. Rate-limited to 30 requests per minute.
-   **Query Parameters:**
    -   `since`: (Optional) An ISO 8601 timestamp; only articles published at or after it. A timestamp without an offset is read as UTC.
    -   `limit`: (Optional) Number of articles, 1–1000. Default 100.
-   **Example Response:**
    ```json
    [
        {
            "_id": "d1a2b3c4...",
            "title": "Example Article Title",
            "link": "http://example.com/article",
            "description": "This is an example article.",
            "published": "2025-12-19T12:00:00Z",
            "feed_url": "http://example.com/rss"
        }
    ]
    ```

### Events

#### Create Event

-   **Method:** `POST`
-   **Path:** `/mcp/events`
-   **Description:** Creates a new event and links it to one or more articles.
-   **Example Request:**
    ```json
    {
        "name": "New AI Breakthrough",
        "description": "A new AI model has been announced.",
        "article_ids": ["d1a2b3c4...", "e5f6g7h8..."]
    }
    ```
-   **Example Response:**
    ```json
    {
        "status": "success",
        "event_id": "i9j0k1l2..."
    }
    ```

#### List Events

-   **Method:** `GET`
-   **Path:** `/mcp/events`
-   **Description:** Retrieves a list of events.
-   **Example Response:**
    ```json
    [
        {
            "_id": "i9j0k1l2...",
            "name": "New AI Breakthrough",
            "description": "A new AI model has been announced.",
            "article_ids": ["d1a2b3c4...", "e5f6g7h8..."]
        }
    ]
    ```

#### Get Event

-   **Method:** `GET`
-   **Path:** `/mcp/events/<event_id>`
-   **Description:** Retrieves a single event by its ID.
-   **Query Parameters:**
    -   `include_articles`: (Optional) A boolean to indicate whether to include the full article objects in the response.
-   **Example Response:**
    ```json
    {
        "_id": "i9j0k1l2...",
        "name": "New AI Breakthrough",
        "description": "A new AI model has been announced.",
        "article_ids": ["d1a2b3c4...", "e5f6g7h8..."]
    }
    ```

### Trends

#### Create Trend

-   **Method:** `POST`
-   **Path:** `/mcp/trends`
-   **Description:** Creates a new trend and links it to one or more events.
-   **Example Request:**
    ```json
    {
        "name": "Rise of Generative AI",
        "description": "A growing trend of new generative AI models being released.",
        "event_ids": ["i9j0k1l2...", "m3n4o5p6..."]
    }
    ```
-   **Example Response:**
    ```json
    {
        "status": "success",
        "trend_id": "q7r8s9t0..."
    }
    ```

#### List Trends

-   **Method:** `GET`
-   **Path:** `/mcp/trends`
-   **Description:** Retrieves a list of trends.
-   **Example Response:**
    ```json
    [
        {
            "_id": "q7r8s9t0...",
            "name": "Rise of Generative AI",
            "description": "A growing trend of new generative AI models being released.",
            "event_ids": ["i9j0k1l2...", "m3n4o5p6..."]
        }
    ]
    ```

#### Get Trend

-   **Method:** `GET`
-   **Path:** `/mcp/trends/<trend_id>`
-   **Description:** Retrieves a single trend by its ID.
-   **Query Parameters:**
    -   `include_events`: (Optional) A boolean to indicate whether to include the full event objects in the response.
    -   `include_articles`: (Optional) A boolean to indicate whether to include the full article objects linked to the events.
-   **Example Response:**
    ```json
    {
        "_id": "q7r8s9t0...",
        "name": "Rise of Generative AI",
        "description": "A growing trend of new generative AI models being released.",
        "event_ids": ["i9j0k1l2...", "m3n4o5p6..."]
    }
    ```
