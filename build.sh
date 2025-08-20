#!/bin/bash
set -e

echo "Building Cross-Pollinator image..."
docker-compose build cross-pollinator

if docker image inspect cross-pollinator:latest >/dev/null 2>&1; then
    echo "Build complete!"
else
    echo "Build failed!"
    exit 1
fi
