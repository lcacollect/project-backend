#! /usr/bin/bash
set -e

export SERVER_NAME="LCA Test"
export SERVER_HOST="http://test"
export PROJECT_NAME="LCA Test"
export POSTGRES_HOST=localhost
export POSTGRES_USER=postgresuser
export POSTGRES_PASSWORD=YWRnYWtqMjM1NGpoc2tsaDc4MzU0
export POSTGRES_DB=project
export POSTGRES_PORT=5433
export AAD_OPENAPI_CLIENT_ID=dafkhlajdhfkjadf
export AAD_APP_CLIENT_ID=dafkhlajdhfkjadf
export AAD_TENANT_ID=dafkhlajdhfkjadf
export AAD_GRAPH_SECRET=PLACEHOLDER
export SENDGRID_SECRET=PLACEHOLDER
export ROUTER_URL=http://router.url
export STORAGE_ACCOUNT_URL=PLACEHOLDER
export STORAGE_CONTAINER_NAME=PALCEHOLDER
export STORAGE_ACCESS_KEY=PLACEHOLDER
export STORAGE_BASE_PATH=PLACEHOLDER

alembic revision --autogenerate