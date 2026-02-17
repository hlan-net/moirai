# Build the Python application using Miniforge
FROM condaforge/miniforge3:24.3.0-0 AS final-stage

# Build arguments for version info
ARG VERSION=0.4.0-rc.3
ARG BUILD_NUMBER=unknown

# Set the working directory in the container
WORKDIR /app

# Combine system and environment setup
COPY environment.yml .
RUN apt-get update && apt-get install -y curl && \
    rm -rf /var/lib/apt/lists/* && \
    conda install -y mamba && \
    mamba env create -f environment.yml && \
    mamba clean --all && \
    useradd -ms /bin/bash appuser && \
    mkdir -p /app/feeds /app/ui/dist /run/gunicorn && \
    chown -R appuser:appuser /app/feeds /app/ui/dist /run/gunicorn

# Set the PATH to include the conda environment's bin directory
ENV PATH="/opt/conda/envs/moirai/bin:$PATH"
ENV BUILD_NUMBER=${BUILD_NUMBER}

# Use root to copy files and set final permissions
USER root
COPY . .

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

# Run the application using Gunicorn
CMD ["conda", "run", "--no-capture-output", "--name", "moirai", "gunicorn", "--config", "gunicorn.conf.py", "main:app"]
