# Moirai Architecture Refactor Plan

This document outlines the plan to refactor the Moirai application architecture to support scalable, robust, and decoupled services in Kubernetes, while maintaining a simple and effective local development environment with Docker Compose.

## 1. Problem Statement

The current architecture runs the API web server, a periodic feed scheduler, and a continuous enrichment worker within the same container/pod. This design prevents the API service from being scaled horizontally (i.e., running more than one replica) because it would lead to multiple instances of the stateful background tasks running concurrently, causing race conditions, database conflicts, and wasted resources.

## 2. Solution Overview: Decouple Services

The solution is to separate the stateless web components from the stateful background workers using a hybrid model that leverages dedicated Kubernetes resources for each task type. This allows the API to be scaled independently to handle user load, while ensuring background tasks run reliably and efficiently.

This plan incorporates the "API + Jobs" model, using a `Deployment` for the continuous worker and a `CronJob` for the periodic scheduler.

## 3. Implementation Plan

The implementation will be executed in three phases:

### Phase 1: Code and Entrypoint Changes

The goal of this phase is to create distinct entrypoints for each process type within the existing API Docker image.

1.  **Modify `main.py` & `gunicorn.conf.py`**:
    *   The `on_starting` hook in `gunicorn.conf.py` that currently calls `start_services()` will be removed.
    *   This ensures that running Gunicorn will *only* start the web server.

2.  **Create `run_worker.py`**:
    *   A new Python script at the root of the project.
    *   **Function:** It will import and call the `start_services()` function (which starts the long-running enrichment worker) and then enter a wait loop to keep the process alive.
    *   **Purpose:** To serve as the dedicated entrypoint for the continuous enrichment worker process.

3.  **Create `run_scheduler.py`**:
    *   A new Python script at the root of the project.
    *   **Function:** It will import and call the scheduler task logic to run exactly once and then exit.
    *   **Purpose:** To serve as the entrypoint for the periodic `CronJob` and for manual runs in the local environment.

### Phase 2: Helm Chart Modifications

This phase adapts the Kubernetes deployment to use the new entrypoints.

1.  **Update `helm/templates/api-deployment.yaml`**:
    *   Ensure its container `command` runs the Gunicorn web server (which will now be the default behavior of the image's CMD).
    *   Expose the `api.replicaCount` value from `values.yaml` so the API can be scaled (e.g., to 3 replicas).

2.  **Add `helm/templates/worker-deployment.yaml`**:
    *   A new `Deployment` template will be created.
    *   It will use the same API Docker image.
    *   Its `replicaCount` will be hardcoded to `1` to ensure only one enrichment worker is active.
    *   Its container `command` will be `["python", "run_worker.py"]`.

3.  **Add `helm/templates/scheduler-cronjob.yaml`**:
    *   A new `CronJob` template will be created.
    *   It will use the same API Docker image.
    *   Its `schedule` will be configurable via `values.yaml` (e.g., `"*/10 * * * *"`).
    *   Its container `command` will be `["python", "run_scheduler.py"]`.
    *   It will include `ttlSecondsAfterFinished: 3600` in its `jobTemplate` to ensure completed jobs are automatically cleaned up by Kubernetes after one hour.

### Phase 3: Local Development Environment Update

This phase ensures the local Docker Compose environment remains fast, simple, and accurately reflects the new architecture.

1.  **Modify `docker-compose.yml`**:
    *   A new service named `worker` will be added.
    *   It will use the same API image as the `api` service.
    *   Its `command` will be `python run_worker.py`.

2.  **Update Developer Documentation (`README.md` or similar)**:
    *   The documentation will be updated to include the new `worker` service.
    *   It will provide the command for running the scheduler manually: `docker compose run --rm api python run_scheduler.py`.
