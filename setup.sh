#!/bin/bash
# Initial setup script

set -e

echo "Setting up Cross-Pollinator..."

# Copy environment file if it doesn't exist
if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env file - please edit paths if needed"
fi

# Make scripts executable
chmod +x build.sh run.sh

# Build initial image
./build.sh

echo "Setup complete!"
echo ""
echo "Quick start:"
echo "  ./run.sh          # Run analysis"
echo "  ./run.sh --stats  # Run with statistics"
