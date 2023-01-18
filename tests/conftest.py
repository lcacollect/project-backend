import time
from typing import Iterator

import docker
import lcacollect_config.security
import pytest
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from httpx import AsyncClient
from lcacollect_config.connection import create_postgres_engine
from sqlmodel import SQLModel

from core.config import settings


@pytest.fixture(scope="session")
def docker_client():
    yield docker.from_env()


@pytest.fixture(scope="session")
def postgres(docker_client):
    container = docker_client.containers.run(
        "postgres:13.1-alpine",
        ports={"5432": settings.POSTGRES_PORT},
        environment={
            "POSTGRES_DB": settings.POSTGRES_DB,
            "POSTGRES_PASSWORD": settings.POSTGRES_PASSWORD,
            "POSTGRES_USER": settings.POSTGRES_USER,
        },
        detach=True,
        auto_remove=True,
    )

    time.sleep(3)
    yield container

    container.stop()


@pytest.fixture()
async def db(postgres) -> None:
    engine = create_postgres_engine()
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)


@pytest.fixture()
def mock_azure_scheme(mocker):
    class ConfigClass:
        def __init__(self):
            pass

        async def load_config(self):
            pass

    class AzureScheme:
        openid_config = ConfigClass()
        # fake user object fields
        access_token = "fake_access_token"
        claims = {"oid": "someid0"}
        roles = []

    mocker.patch.object(
        lcacollect_config.security,
        "azure_scheme",
        AzureScheme,
    )


@pytest.fixture()
async def app(db, mock_azure_scheme) -> FastAPI:

    from main import app

    async with LifespanManager(app):
        yield app


@pytest.fixture()
async def client(app: FastAPI) -> Iterator[AsyncClient]:
    """Async server (authenticated) client that handles lifespan and teardown"""

    async with AsyncClient(
        app=app,
        base_url=settings.SERVER_HOST,
        headers={"authorization": f"Bearer eydlhjaflkjadh"},
    ) as _client:
        try:
            yield _client
        except Exception as exc:
            print(exc)
