# Stage 1: Build the conda environment
FROM condaforge/miniforge3:26.1.0-0@sha256:df8d10c338351cc245f687c62921f40c8c1664249594b3b1cad37ae5f5ee7483 AS builder

WORKDIR /build

COPY environment-prod.yml .
RUN conda install -y mamba && \
    mamba env create -f environment-prod.yml && \
    mamba clean --all --force-pkgs-dirs -y && \
    # ---- Aggressively strip the conda env for production ----
    # 1. Google API discovery cache (93 MB of JSON, fetched at runtime anyway)
    rm -rf /opt/conda/envs/moirai/lib/python3.10/site-packages/googleapiclient/discovery_cache/documents && \
    # 2. pip and setuptools (not needed at runtime)
    pip install --target /dev/null 2>/dev/null; \
    rm -rf /opt/conda/envs/moirai/lib/python3.10/site-packages/pip \
           /opt/conda/envs/moirai/lib/python3.10/site-packages/setuptools \
           /opt/conda/envs/moirai/lib/python3.10/site-packages/pkg_resources \
           /opt/conda/envs/moirai/lib/python3.10/ensurepip && \
    # 3. Tkinter / tcl / tk (not needed for a web server)
    rm -rf /opt/conda/envs/moirai/lib/libtcl* \
           /opt/conda/envs/moirai/lib/libtk* \
           /opt/conda/envs/moirai/lib/tcl8* \
           /opt/conda/envs/moirai/lib/tk8* \
           /opt/conda/envs/moirai/lib/python3.10/tkinter \
           /opt/conda/envs/moirai/lib/python3.10/lib-tk && \
    # 4. C headers and static libraries (only needed for compiling)
    rm -rf /opt/conda/envs/moirai/include \
           /opt/conda/envs/moirai/lib/*.a && \
    # 5. Share directory (man pages, docs, terminfo, etc.)
    rm -rf /opt/conda/envs/moirai/share/man \
           /opt/conda/envs/moirai/share/doc \
           /opt/conda/envs/moirai/share/terminfo \
           /opt/conda/envs/moirai/share/gtk-doc && \
    # 6. Python bytecache, test suites, dist-info overhead
    find /opt/conda/envs/moirai -name '*.pyc' -delete && \
    find /opt/conda/envs/moirai -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null; \
    find /opt/conda/envs/moirai -name 'tests' -type d -exec rm -rf {} + 2>/dev/null; \
    find /opt/conda/envs/moirai -name 'test' -type d -exec rm -rf {} + 2>/dev/null; \
    # 7. Strip debug symbols from shared libraries
    find /opt/conda/envs/moirai -name '*.so*' -exec strip --strip-unneeded {} + 2>/dev/null; \
    true

# Stage 2: Slim runtime image
FROM debian:bookworm-slim@sha256:98f4b71de414932439ac6ac690d7060df1f27161073c5036a7553723881bffbe AS final-stage

# Install only curl (health probes) and CA certs (HTTPS).
# libffi, libssl, libgomp are already inside the conda env.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
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
