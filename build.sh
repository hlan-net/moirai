#!/bin/bash
# Build script for Moirai with version and build number

VERSION="0.1.0"
BUILD_NUMBER="${1:-$(git rev-parse --short HEAD 2>/dev/null || echo 'dev')}"

echo "Building Moirai v${VERSION} (build ${BUILD_NUMBER})"

docker build \
  --build-arg VERSION="${VERSION}" \
  --build-arg BUILD_NUMBER="${BUILD_NUMBER}" \
  -t ghcr.io/hlan-net/moirai:${VERSION}-${BUILD_NUMBER} \
  -t ghcr.io/hlan-net/moirai:latest \
  .

echo "Built: ghcr.io/hlan-net/moirai:${VERSION}-${BUILD_NUMBER}"
echo "Tagged: ghcr.io/hlan-net/moirai:latest"
