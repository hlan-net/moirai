# Stage 1: Build the Vue.js application
FROM node:25-alpine@sha256:cf38e1f3c28ac9d81cdc0c51d8220320b3b618780e44ef96a39f76f7dbfef023 AS build-stage

WORKDIR /app

# Copy package.json and yarn.lock to leverage Docker cache
COPY package.json yarn.lock ./

# Install dependencies (resolutions in package.json will handle entities)
RUN yarn install

# Copy the rest of the UI source code
COPY . .

# Build arguments placed after dependency install so they don't bust the cache
ARG APP_VERSION=dev
ARG BUILD_NUMBER=unknown
ENV APP_VERSION=${APP_VERSION}
ENV BUILD_NUMBER=${BUILD_NUMBER}

# Create build-info.json for runtime version display
RUN mkdir -p /app/public && \
    printf '{"appVersion":"%s","buildNumber":"%s"}\n' "${APP_VERSION}" "${BUILD_NUMBER}" > /app/public/build-info.json

# Build the application
RUN yarn build

# Stage 2: Serve the application with Nginx
FROM nginx:stable-alpine@sha256:a8b39bd9cf0f83869a2162827a0caf6137ddf759d50a171451b335cecc87d236

# Build arguments for version info
ARG APP_VERSION=dev
ARG BUILD_NUMBER=unknown

# Copy the built files from the build stage
COPY --from=build-stage /app/dist /usr/share/nginx/html

# Copy the Nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Create build info files
RUN mkdir -p /etc/moirai && \
    printf "APP_VERSION=%s\nBUILD_NUMBER=%s\n" "${APP_VERSION}" "${BUILD_NUMBER}" > /etc/moirai/build-info && \
    chmod 644 /etc/moirai/build-info && \
    printf '{"appVersion":"%s","buildNumber":"%s"}\n' "${APP_VERSION}" "${BUILD_NUMBER}" > /usr/share/nginx/html/build-info.json

# Expose port 80
EXPOSE 80

# Start Nginx
CMD ["nginx", "-g", "daemon off;"]
