# Stage 1: Build the Vue.js application
FROM node:20 AS build-stage

# Set the working directory in the container
WORKDIR /app

# Copy the package.json and yarn.lock
COPY ui/package.json ui/yarn.lock ./

# Install dependencies - this layer is cached unless package.json or yarn.lock changes
RUN yarn install

# Copy the rest of the UI code and build it
COPY ui/ .
RUN yarn build

# Stage 2: Build the Python application
FROM python:3-slim AS final-stage

# Build arguments for version info
ARG VERSION=0.1.0
ARG BUILD_NUMBER=unknown

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file and install dependencies
COPY requirements.txt .
RUN apt-get update && apt-get install -y ca-certificates && rm -rf /var/lib/apt/lists/*
RUN useradd -d /app appuser  && \
    pip install --no-cache-dir -r requirements.txt && \
    mkdir -p feeds && \
    chmod 777 feeds && \
    mkdir -p ui/dist && \
    chown -R appuser:appuser feeds ui

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

# Copy the built UI from the previous stage
COPY --from=build-stage /app/dist/ ./ui/dist/
# Create empty ui/dist to avoid FileNotFoundError in main.py. Do this BEFORE switching user or as root.
# (But here we are already USER appuser from line 36).
# So we should switch back to root or do it earlier.
# Let's do it earlier.


# Expose port 8088 for the Flask app
EXPOSE 8088

# Run the application
CMD ["python", "/app/main.py"]
