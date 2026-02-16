# Build the Python application using Miniforge
FROM condaforge/miniforge3:24.3.0-0 AS final-stage

# Build arguments for version info
ARG VERSION=0.3.0
ARG BUILD_NUMBER=unknown

# Set the working directory in the container
WORKDIR /app

# Install curl
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Install mamba (faster conda operations)
RUN conda install -y mamba

# Copy environment.yml and install dependencies
COPY environment.yml .
RUN mamba env create -f environment.yml && \
    mamba clean --all

# Copy and make executable the database initialization script (as root)
COPY create_dbs.sh /app/create_dbs.sh
RUN chmod +x /app/create_dbs.sh

# Activate the environment and set up appuser
# Use a non-root user (appuser) for security
RUN useradd -ms /bin/bash appuser && \
    chown -R appuser:appuser /app && \
    mkdir -p /app/feeds && \
    chmod 700 /app/feeds && \
    mkdir -p /app/ui/dist && \
    chown -R appuser:appuser /app/ui/dist

# Set the PATH to include the conda environment's bin directory
ENV PATH="/opt/conda/envs/moirai/bin:$PATH"

USER appuser

# Set build number as environment variable
ENV BUILD_NUMBER=${BUILD_NUMBER}

# Copy the rest of the application code into the container
COPY --chown=appuser:appuser main.py .
COPY --chown=appuser:appuser mcp_server.py .
COPY --chown=appuser:appuser version.py .
COPY --chown=appuser:appuser api/ api/
COPY --chown=appuser:appuser tasks/ tasks/
COPY --chown=appuser:appuser mcp_service/ mcp_service/
COPY --chown=appuser:appuser gunicorn.conf.py .



# Expose port 8088 for the Flask app
EXPOSE 8088

# Run the application
CMD ["conda", "run", "--name", "moirai", "python", "/app/main.py"]