# Moirai Refactoring Status: UI/API Split and Helm Chart Update

## Project Context
This document summarizes the significant architectural refactoring undertaken to split the Moirai application into distinct UI and API services, managed by a new Nginx reverse proxy. The primary goals were to improve maintainability, enable independent scaling, and align with modern microservice best practices.

## Completed Work

### 1. Docker Container Split
*   **`Dockerfile` (Root):** Simplified to build only the Python API backend, removing all Node.js and UI build stages.
*   **`ui/Dockerfile`:** Created a new multi-stage Dockerfile dedicated to building the Vue.js frontend and serving it with Nginx.
*   **`ui/nginx.conf`:** Created an Nginx configuration file within the `ui` directory for serving static UI assets and demonstrating API proxying for local Docker Compose development.
*   **`docker-compose.yml`:** Updated to define three separate services:
    *   `api`: The Python Flask backend, built from the root `Dockerfile`.
    *   `ui`: The Vue.js frontend, built from `ui/Dockerfile`, internally served by Nginx.
    *   `nginx`: A top-level Nginx reverse proxy that routes requests to either `api` (for `/api` paths) or `ui` (for all other paths). This proxy is the primary entry point for the application (`http://localhost:8088`).

### 2. Helm Chart Updates
The Helm chart (`helm/`) has been extensively refactored to support the new service architecture:

*   **`helm/values.yaml`:**
    *   Removed top-level `image` and `service` configurations.
    *   Introduced new, granular configuration sections for `api`, `ui`, and `nginx` services, each with its own `image`, `replicaCount`, and `service` settings.
    *   `appVersion` was corrected back to `0.3.1` as no new application release has occurred yet, while the chart `version` was incremented to `0.3.1`.
*   **`helm/templates/api-deployment.yaml` & `helm/templates/api-service.yaml`:**
    *   The former `moirai-deployment.yaml` and `moirai-service.yaml` were renamed and modified to specifically deploy and expose the `api` service.
    *   The `app.kubernetes.io/component` label was updated to `api`.
    *   The `initContainers` responsible for CouchDB database initialization were removed from the `api-deployment.yaml` as this responsibility is now shifted to the `mcp-server` init container for centralized database setup.
*   **`helm/templates/ui-deployment.yaml` & `helm/templates/ui-service.yaml`:**
    *   New Kubernetes manifests to deploy and expose the `ui` service.
    *   The `app.kubernetes.io/component` label is set to `ui`.
*   **`helm/templates/nginx-configmap.yaml`:**
    *   A new ConfigMap to hold the `nginx.conf` for the Kubernetes `nginx` reverse proxy, defining routing rules for `/` (to `ui`) and `/api` (to `api`).
*   **`helm/templates/nginx-deployment.yaml` & `helm/templates/nginx-service.yaml`:**
    *   New Kubernetes manifests to deploy and expose the `nginx` reverse proxy.
    *   The `nginx-configmap` is mounted into the Nginx container.
    *   The `app.kubernetes.io/component` label is set to `nginx`.
*   **`helm/templates/ingress.yaml`:**
    *   Updated to point all incoming traffic to the `nginx` service, which then handles internal routing to `api` and `ui`.
*   **`helm/templates/_helpers.tpl`:**
    *   Updated to include new helper definitions for generating names and labels specific to the `api`, `ui`, and `nginx` components.
*   **`helm/Chart.yaml`:**
    *   `version` incremented to `0.3.1`.
    *   `appVersion` set to `0.3.1`.

### 3. Verification
*   **Local Docker Compose:** The refactored Docker Compose setup starts all services (`api`, `ui`, `nginx`, `mcp-server`, `couchdb`, `redis`) correctly. The application is fully accessible via the `nginx` proxy on `http://localhost:8088`.

## Current Branch Status
All changes described above are committed to the `feature/parallelism-support` branch and pushed to the remote repository.

## Next Steps for Continuation and Deployment

To deploy these changes to a Kubernetes environment or continue development:

1.  **Merge Pull Request:** Merge the `feature/parallelism-support` branch into your main development branch (e.g., `main` or `master`). This action should ideally trigger your CI/CD pipeline.
2.  **Trigger CI/CD (if not automated):**
    *   Ensure your CI/CD pipeline builds new Docker images for the `moirai-api` and `moirai-ui` services based on the updated Dockerfiles.
    *   Verify that these images are pushed to your container registry (e.g., GHCR).
    *   Publish the updated Helm chart (version `0.3.1`) to your Helm chart repository.
3.  **Review `values.yaml`:** Before deploying, review your specific Kubernetes deployment `values.yaml` file to ensure that all `api`, `ui`, and `nginx` configurations, especially image tags, resource limits, and ingress settings, align with your deployment environment.
4.  **Helm Upgrade:** Execute the Helm upgrade command to apply the new chart to your Kubernetes cluster:
    ```bash
    helm upgrade --install moirai oci://ghcr.io/hlan-net/charts/moirai:0.3.1 -f your-values.yaml --namespace moirai
    ```
    (Adjust `0.3.1` to the actual chart version if it changes, and `your-values.yaml` to your specific values file.)
5.  **Monitor Deployment:** Observe the deployment status in Kubernetes to ensure all new pods (for `api`, `ui`, `nginx`) start successfully and services are accessible.

This document provides a clear path forward for managing and deploying the newly structured Moirai application.
