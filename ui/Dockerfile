# Stage 1: Build the Vue.js application
ARG BUILDPLATFORM
ARG TARGETPLATFORM
FROM --platform=$BUILDPLATFORM node:25-alpine@sha256:18e02657e2a2cc3a87210ee421e9769ff28a1ac824865d64f74d6d2d59f74b6b AS build-stage

WORKDIR /app

# Copy package.json and yarn.lock to leverage Docker cache
COPY package.json yarn.lock ./

# Install dependencies (resolutions in package.json will handle entities)
RUN yarn install

# Copy the rest of the UI source code
COPY . .

# Build argument placed after dependency install so it doesn't bust the cache
ARG BUILD_NUMBER
ENV BUILD_NUMBER=$BUILD_NUMBER

# Build the application
RUN yarn build

# Stage 2: Serve the application with Nginx
FROM --platform=$TARGETPLATFORM nginx:stable-alpine@sha256:15e96e59aa3b0aada3a121296e3bce117721f42d88f5f64217ef4b18f458c6ab

# Copy the built files from the build stage
COPY --from=build-stage /app/dist /usr/share/nginx/html

# Copy the Nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port 80
EXPOSE 80

# Start Nginx
CMD ["nginx", "-g", "daemon off;"]
