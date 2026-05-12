# External REST API Documentation

## Note
This documentation describes the **REST API endpoints** served by the Flask backend (Port 8088) under the `/mcp` prefix. 

**This is NOT the Model Context Protocol (MCP) Server.**
The actual MCP Server runs on Port 8090 via SSE (Server-Sent Events) and is designed for direct connection with MCP clients (like Claude Desktop or the Moirai Chat Agent).

These REST endpoints are provided for external non-MCP services or legacy integrations that need to access the data via standard HTTP methods.

## Introduction

The External API provides a set of RESTful endpoints...

## Endpoints

### Articles

#### Retrieve Articles

-   **Method:** `GET`
-   **Path:** `/mcp/articles`
-   **Description:** Retrieves a list of articles.
-   **Query Parameters:**
    -   `since`: (Optional) A timestamp in ISO 8601 format to retrieve articles published after a certain date.
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
