# Stage 1: Build the Vue.js application
FROM node:14 AS build-stage

# Set the working directory in the container
WORKDIR /app

# Copy the package.json and install dependencies
COPY ui/package.json ui/yarn.lock ./
RUN yarn install

# Copy the rest of the UI code and build it
COPY ui/ .
RUN yarn build

# Stage 2: Build the Python application
FROM python:3.9-slim AS final-stage

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    useradd -m appuser
USER appuser

# Copy the built UI from the previous stage
COPY --from=build-stage /app/dist ./ui

# Copy the rest of the application code into the container
COPY main.py .

COPY api/ api/

# Expose port 80 for the Flask app
EXPOSE 80

# Run the application
CMD ["python", "main.py"]
