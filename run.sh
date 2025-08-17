#!/bin/bash
set -e

STATS_FLAG=""
if [[ "$1" == "--stats" ]]; then
    STATS_FLAG="--stats"
fi

if ! docker image inspect cross-pollinator:latest >/dev/null 2>&1; then
    echo "🔨 Building image..."
    ./build.sh
fi

echo "🚀 Running Cross-Pollinator analysis..."
docker-compose run --rm cross-pollinator --run $STATS_FLAG
