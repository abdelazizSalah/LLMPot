#!/bin/bash
set -e
sudo docker compose -f compose.prod.yaml down
sudo docker compose -f compose.prod.yaml up -d --build
sudo docker logs llmpot-web --tail 100