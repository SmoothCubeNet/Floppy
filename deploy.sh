#!/bin/bash

set -e

CONTAINER_NAME="Floppy"

echo "📥 Pulling latest code..."
git pull

echo "🛑 Stopping existing container (if running)..."
sudo docker stop $CONTAINER_NAME 2>/dev/null || true

echo "🧹 Removing old container..."
sudo docker rm $CONTAINER_NAME 2>/dev/null || true

echo "🏗️ Building temporary image..."
IMAGE_ID=$(sudo docker build -q .)

echo "🚀 Starting new container..."
sudo docker run -d \
  --name $CONTAINER_NAME \
  --restart unless-stopped \
  $IMAGE_ID

echo "🧽 Cleaning up dangling images..."
sudo docker image prune -f

echo "✅ Done. Container '$CONTAINER_NAME' is running."
