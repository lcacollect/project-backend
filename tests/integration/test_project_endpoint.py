import asyncio

import httpx
import pytest
from httpx import AsyncClient
from pytest_httpx import HTTPXMock
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from core.config import settings
from core.federation import (
    GraphQLProjectSource,
    delete_project_source,
    delete_reporting_schema,
    get_reporting_schema,
    get_source,
)
from models.project import Project


@pytest.mark.asyncio
async def test_get_projects(client: AsyncClient, project_with_members):

    query = """
        query {
            projects {
                name
            }
        }
    """

    response = await client.post(f"{settings.API_STR}/graphql", json={"query": query, "variables": None})

    assert response.status_code == 200
    data = response.json()
    print(data)
    assert not data.get("errors")
    assert data["data"]["projects"] == [
        {"name": "Project 0"},
        {"name": "Project 0"},
        {"name": "Project 1"},
        {"name": "Project 2"},
    ]


@pytest.mark.asyncio
async def test_get_projects_with_filters(client: AsyncClient, project_with_members):

    query = """
        query($name: String!) {
            projects(filters: {name: {equal: $name}}) {
                name
            }
        }
    """

    response = await client.post(
        f"{settings.API_STR}/graphql",
        json={"query": query, "variables": {"name": project_with_members.name}},
    )

    assert response.status_code == 200
    data = response.json()
    print(data)

    assert not data.get("errors")
    assert len(data["data"]["projects"]) == 2
    assert data["data"]["projects"][0] == {"name": project_with_members.name}


@pytest.mark.asyncio
async def test_create_project(client: AsyncClient, projects):
    query = """
        mutation($projectId: String!){
            addProject(projectId: $projectId, name: "myProject") {
                name
            }
        }
    """

    response = await client.post(
        f"{settings.API_STR}/graphql",
        json={"query": query, "variables": {"projectId": projects[0].project_id}},
    )

    assert response.status_code == 200
    data = response.json()

    assert not data.get("errors")
    assert data["data"]["addProject"] == {
        "name": f"myProject",
    }


@pytest.mark.asyncio
async def test_create_project_with_picture(client: AsyncClient, base64_encoded_image: str, mocker):
    mocker.patch("azure.storage.blob.aio.BlobClient.upload_blob", return_value=asyncio.Future())

    query = """
    mutation(
        $name: String!
        $projectId: String!
        $client: String
        $file: String
    ){
        addProject(
            name: $name
            projectId: $projectId
            client: $client
            file: $file
        ){
            name
            projectId
            client
            imageUrl
        }
    }
    """
    response = await client.post(
        f"{settings.API_STR}/graphql",
        json={
            "query": query,
            "variables": {
                "name": "Business Garden",
                "projectId": "COWI LT",
                "client": "Some Client's Name",
                "file": base64_encoded_image,
            },
        },
    )
    assert response.status_code == 200
    data = response.json()

    assert not data.get("errors")
    assert data["data"]["addProject"] == {
        "name": "Business Garden",
        "projectId": "COWI LT",
        "client": "Some Client's Name",
        "imageUrl": "https://documentationbundle.blob.core.windows.net/PLACEHOLDER/"
        "test/c2/ee/cdd112b12b23477c82300c5205e641171e57493b6e52e3c1a18c84815f76",
    }


@pytest.mark.asyncio
async def test_update_project(client: AsyncClient, mock_members_from_azure, project_with_members):

    query = """
        mutation(
            $name: String, $id: String!, $client: String! $address: String! $city: String! $country: String! 
        ) {
            updateProject(
                name: $name, id: $id, client: $client, address: $address city: $city
                country: $country
            ) {
                name
                client
                address
                city
                country
            }
        }
    """

    response = await client.post(
        f"{settings.API_STR}/graphql",
        json={
            "query": query,
            "variables": {
                "name": project_with_members.name,
                "id": project_with_members.id,
                "client": "Some Client's Name",
                "address": "Next to Rådhuspladsen",
                "country": "Denmark",
                "city": "København",
            },
        },
    )

    assert response.status_code == 200
    data = response.json()

    assert not data.get("errors")
    assert data["data"]["updateProject"] == {
        "name": project_with_members.name,
        "client": "Some Client's Name",
        "country": "Denmark",
        "city": "København",
        "address": "Next to Rådhuspladsen",
    }


@pytest.mark.asyncio
async def test_delete_project(client: AsyncClient, projects, db, httpx_mock: HTTPXMock, mocker):

    reporting_schemas_mock = {
        "data": {
            "reportingSchemas": [
                {
                    "id": "1010101-ce95-49cf-b45d-5b0a867a4a17",
                    "projectId": projects[0].id,
                }
            ]
        }
    }
    schema_sources_mock = {
        "data": {
            "projectSources": [
                {
                    "id": "1010101-ce95-49cf-b45d-5b0a867a4a17",
                    "authorId": "1010101-ce95-49cf-b45d-5b0a867a4a17",
                    "projectId": projects[0].id,
                }
            ]
        }
    }
    reporting_schemas_delete_mock = {
        "data": {
            "deleteReportingSchema": {
                "id": "1010101-ce95-49cf-b45d-5b0a867a4a17",
            }
        }
    }
    schema_sources_delete_mock = {
        "data": {
            "deleteProjectSource": {
                "id": "1010101-ce95-49cf-b45d-5b0a867a4a17",
            }
        }
    }

    httpx_mock.add_response(
        url=f"{settings.ROUTER_URL}/graphql",
        json=reporting_schemas_mock,
        match_content=b'{"query": "\\n        query($projectId: String!) {\\n            reportingSchemas(projectId: $projectId) {\\n                id\\n                projectId\\n            }\\n        }\\n    ", "variables": {"projectId": "'
        + projects[0].id.encode()
        + b'"}}',
    )
    httpx_mock.add_response(
        url=f"{settings.ROUTER_URL}/graphql",
        json=schema_sources_mock,
        match_content=b'{"query": "\\n        query($projectId: String!) {\\n            projectSources(projectId: $projectId) {\\n                id\\n                authorId\\n                projectId\\n            }\\n        }\\n    ", "variables": {"projectId": "'
        + projects[0].id.encode()
        + b'"}}',
    )
    httpx_mock.add_response(
        url=f"{settings.ROUTER_URL}/graphql",
        json=reporting_schemas_delete_mock,
        match_content=b'{"query": "\\n        mutation($id: String!) {\\n            deleteReportingSchema(id: $id) {\\n                id\\n            }\\n        }\\n    ", "variables": {"id": "1010101-ce95-49cf-b45d-5b0a867a4a17"}}',
    )
    httpx_mock.add_response(
        url=f"{settings.ROUTER_URL}/graphql",
        json=schema_sources_delete_mock,
        match_content=b'{"query": "\\n        mutation($id: String!) {\\n            deleteProjectSource(id: $id) {\\n                id\\n            }\\n        }\\n    ", "variables": {"id": "1010101-ce95-49cf-b45d-5b0a867a4a17"}}',
    )

    query = """
        mutation($id: String!) {
            deleteProject(id: $id)
        }
    """

    response = await client.post(
        f"{settings.API_STR}/graphql",
        json={"query": query, "variables": {"id": projects[0].id}},
    )
    assert response.status_code == 200
    data = response.json()

    assert not data.get("errors")

    async with AsyncSession(db) as session:
        query = select(Project)
        _projects = await session.exec(query)
        _projects = _projects.all()

    assert len(_projects) == len(projects) - 1