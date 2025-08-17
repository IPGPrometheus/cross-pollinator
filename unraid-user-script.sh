#!/bin/bash
# Cross-Pollinator Unraid User Script
# Add this to User Scripts for scheduled runs

cd /mnt/user/appdata/cross-pollinator

# Ensure image exists
if ! docker image inspect cross-pollinator:latest >/dev/null 2>&1; then
    echo "🔨 Building Cross-Pollinator image..."
    ./build.sh
fi

# Run analysis with stats
echo "🚀 Running Cross-Pollinator analysis..."
./run.sh --stats

echo "✅ Cross-Pollinator run complete!"
