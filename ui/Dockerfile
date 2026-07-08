# Stage 1: Build the Vue.js application
FROM node:22-slim AS build-stage

WORKDIR /app

# Copy package.json, yarn.lock and .yarnrc.yml to leverage Docker cache
# (.yarnrc.yml sets nodeLinker: node-modules — must be present before install
# or Yarn 4 defaults to PnP and yarn build fails to find the node_modules state file)
COPY package.json yarn.lock .yarnrc.yml ./

# Enable corepack so yarn is available (bundled in node:22 but disabled by default)
RUN corepack enable && yarn install

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
FROM nginx:stable-alpine@sha256:6525b050aa05151ca19ec7090851bc8c12006cffdae5187f3d28023402f44cfa

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
