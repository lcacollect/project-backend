# Introduction

This repo is a [git submodule](https://git-scm.com/book/en/v2/Git-Tools-Submodules). Thus changes made here will be
reflected in external sources, which requires a certain workflow to ensure consistency for all developers who depend on
this repo.
Besides that it functions as any other repo.

# Getting Started

To get started please make sure that the following pieces of software are installed on your machine.

# Software dependencies

## Windows

- [WSL](https://docs.microsoft.com/en-us/windows/wsl/install-win10)
- [Docker](https://docs.docker.com/desktop/windows/install/)
- [Minikube](https://minikube.sigs.k8s.io/docs/start/)
- [Skaffold](https://skaffold.dev/docs/install/#standalone-binary)
- [Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli-windows?tabs=azure-cli)
- Python 3.10
- [pipenv](https://pipenv.pypa.io/en/latest/#install-pipenv-today)
- [pre-commit](https://pre-commit.com/#installation)

## Linux

- [Docker](https://docs.docker.com/engine/install/ubuntu/)
- [Minikube](https://minikube.sigs.k8s.io/docs/start/)
- [Skaffold](https://skaffold.dev/docs/install/#standalone-binary)
- [Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli-linux?pivots=apt)
- Python 3.10
- [pipenv](https://pipenv.pypa.io/en/latest/#install-pipenv-today)
- [pre-commit](https://pre-commit.com/#installation)

## Getting the backend up and running

**Setup local `.env`**
Copy the contents of `.env.example` to a local `.env` file.

**Install dependencies**
```shell
# Set environment variables on linux
export ARTIFACTS_TOKEN_BACKEND_PACKAGES=<YOUR_PAT>

# Set environment variables on Windows
$env:ARTIFACTS_TOKEN_BACKEND_PACKAGES=<YOUR_PAT>
# Install packages
pipenv install --dev

# Install pre-commit hooks
pre-commit install
```
See more about Windows Env vars [here](https://www.tutorialspoint.com/how-to-set-environment-variables-using-powershell)

**Start dev server**

Remember to source the .env file before starting Skaffold
To set the content of the .env file as env vars run `export $(grep -v '^#' .env | xargs)`

```shell
# Start Minikube to run a local Kubernetes cluster
minikube start

# Set ENV
export $(grep -v '^#' .env | xargs)

# Run Skaffold
skaffold dev
```

**Run tests locally**

```shell
pytest tests/
```

**Make migration**
Skaffold should be running!

```shell
./local_migration.sh
```

**Export GraphQL schema**

```shell
./export_schema.sh
```

# Folder Structure

```python
alembic /  # Contains migrations
graphql /  # Contains graphql schema for the gateway
helm /  # helm chart for deployment
src /  # source code
    core /  # code related to FastAPI/webserver
    exceptions /  # custom exceptions
    models /  # database models
    routes /  # api routes
    schema /  # graphql schema definitions
tests /  # test code
```
