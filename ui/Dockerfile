# Stage 1: Build the Vue.js application
FROM node:26-slim AS build-stage

WORKDIR /app

# Copy package.json, yarn.lock and .yarnrc.yml to leverage Docker cache
# (.yarnrc.yml sets nodeLinker: node-modules — must be present before install
# or Yarn 4 defaults to PnP and yarn build fails to find the node_modules state file)
COPY package.json yarn.lock .yarnrc.yml ./

# Node 26 slim doesn't ship corepack by default; install it (pinned, no lifecycle
# scripts) to activate the pinned Yarn version
ENV YARN_ENABLE_SCRIPTS=false
RUN npm install -g --ignore-scripts corepack@0.35.0 \
    && corepack enable \
    && corepack prepare yarn@4.1.0 --activate \
    && yarn install --immutable

# Copy the rest of the UI source code
COPY . .

# Re-run install after source copy so Yarn's install state matches the final workspace
RUN yarn install --immutable

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
FROM nginx:stable-alpine@sha256:0d3b80406a13a767339fbe2f41406d6c7da727ab89cf8fae399e81f780f814d1

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
