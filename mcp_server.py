from mcp_service.main import app  # noqa: F401

if __name__ == "__main__":
    import uvicorn
    import os
    
    # Run the server using SSE transport on port 8090
    host = os.environ.get("HTTP_HOST", "0.0.0.0")
    uvicorn.run("mcp_server:app", host=host, port=8090, reload=False)
