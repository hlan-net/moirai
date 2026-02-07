if __name__ == "__main__":
    from version import get_version_string
    import uvicorn
    
    # Print version info
    print(f"{get_version_string()} starting...", flush=True)
    
    # Run the server using SSE transport on port 8090
    uvicorn.run("mcp_service.main:app", host="0.0.0.0", port=8090, reload=False)

