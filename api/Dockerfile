# Stage 1: Build the conda environment
FROM condaforge/miniforge3:24.3.0-0 AS builder

WORKDIR /build

COPY environment-prod.yml .
RUN conda install -y mamba && \
    mamba env create -f environment-prod.yml && \
    mamba clean --all --force-pkgs-dirs -y && \
    # Remove pyc files and test dirs to shrink the env
    find /opt/conda/envs/moirai -name '*.pyc' -delete && \
    find /opt/conda/envs/moirai -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null; \
    find /opt/conda/envs/moirai -name 'tests' -type d -exec rm -rf {} + 2>/dev/null; \
    find /opt/conda/envs/moirai -name 'test' -type d -exec rm -rf {} + 2>/dev/null; \
    true

# Stage 2: Slim runtime image
FROM debian:bookworm-slim AS final-stage

# Install only the minimal runtime libraries needed by compiled Python packages
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        libffi8 \
        libssl3 \
        libgomp1 \
        ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -ms /bin/bash appuser && \
    mkdir -p /app/feeds /app/ui/dist /run/gunicorn && \
    chown -R appuser:appuser /app/feeds /app/ui/dist /run/gunicorn

# Copy the conda environment from builder (cached unless environment-prod.yml changes)
COPY --from=builder /opt/conda/envs/moirai /opt/conda/envs/moirai

# Set the PATH to include the conda environment's bin directory
ENV PATH="/opt/conda/envs/moirai/bin:$PATH"

WORKDIR /app

# Copy application code (this layer changes on every code commit)
COPY . .

# Build arguments placed late so they don't bust earlier layer caches
ARG VERSION=0.5.2-dev
ARG BUILD_NUMBER=unknown
ENV BUILD_NUMBER=${BUILD_NUMBER}

# Final permission lockdown
RUN chown -R root:appuser /app && \
    chmod -R 550 /app && \
    chmod -R 700 /app/feeds && \
    chmod -R 770 /app/ui/dist && \
    chmod +x /app/create_dbs.sh && \
    chmod 1777 /tmp

USER appuser

# Expose port 8088 for the Flask app
EXPOSE 8088

# Run the application using Gunicorn directly (no conda run wrapper needed)
CMD ["gunicorn", "--config", "gunicorn.conf.py", "main:app"]
