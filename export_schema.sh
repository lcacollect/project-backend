#! /usr/bin/bash
set -e

# Make sure the folder exist
mkdir -p graphql

export SERVER_NAME="LCA Test"
export SERVER_HOST="http://test"
export PROJECT_NAME="LCA Test"
export POSTGRES_HOST=localhost
export POSTGRES_USER=postgresuser
export POSTGRES_PASSWORD=PLACEHOLDER
export POSTGRES_DB=project
export POSTGRES_PORT=5433
export AAD_OPENAPI_CLIENT_ID=PLACEHOLDER
export AAD_APP_CLIENT_ID=PLACEHOLDER
export AAD_TENANT_ID=PLACEHOLDER
export AAD_GRAPH_SECRET=PLACEHOLDER
export SENDGRID_SECRET=PLACEHOLDER
export ROUTER_URL=http://router.url
export STORAGE_ACCOUNT_URL=PALCEHOLDER
export STORAGE_CONTAINER_NAME=PALCEHOLDER
export STORAGE_ACCESS_KEY=PLACEHOLDER
export STORAGE_BASE_PATH=test

# Export GraphQL schema
BASEDIR=$(dirname $0)
echo "Exporting GraphQL schema to: $BASEDIR/graphql/schema.graphql"
strawberry export-schema --app-dir $BASEDIR/src schema > $BASEDIR/graphql/schema.graphql
