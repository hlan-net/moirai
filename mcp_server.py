if __name__ == "__main__":
    from version import get_version_string
    import uvicorn
    import logging

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    # Print version info
    logger.info(f"{get_version_string()} starting...")

    import os
    # Run the server using SSE transport on port 8090
    host = os.environ.get("HTTP_HOST", "0.0.0.0")
    uvicorn.run("mcp_server:app", host=host, port=8090, reload=False)
