#!/bin/bash

set -e

CONTAINER_NAME="Floppy"

git fetch --all
git reset --hard origin/main

docker stop $CONTAINER_NAME 2>/dev/null || true
docker rm $CONTAINER_NAME 2>/dev/null || true

docker build --iidfile image_id.txt .
IMAGE_ID=$(cat image_id.txt)

docker run -d \
  --name $CONTAINER_NAME \
  --restart unless-stopped \
  --env-file .env \
  -p 8080:8080 \
  $IMAGE_ID

docker image prune -f

docker logs -f $CONTAINER_NAME
