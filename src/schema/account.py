import datetime

import strawberry
from azure.storage.blob import (
    BlobSasPermissions,
    BlobServiceClient,
    generate_container_sas,
)
from lcacollect_config.context import get_user
from strawberry.types import Info

from core.config import settings


@strawberry.type
class GraphQLUserAccount:
    id: str
    tenant_id: str
    name: str
    roles: list[str]
    email: str
    blob_sas_token: str


async def account_query(info: Info) -> GraphQLUserAccount:
    """Get current user"""

    account = get_user(info)
    blob_field = []
    if account_field := [field for field in info.selected_fields if field.name == "account"]:
        blob_field = [field for field in account_field[0].selections if field.name == "blobSasToken"]

    return GraphQLUserAccount(
        id=account.claims.get("oid", ""),
        tenant_id=account.tid,
        name=account.name,
        roles=account.roles,
        email=account.claims.get("preferred_username", ""),
        blob_sas_token=create_service_sas_blob() if len(blob_field) else "",
    )


def create_service_sas_blob() -> str:
    """Create a service SAS token to access a blob"""

    start_time = datetime.datetime.now(datetime.timezone.utc)
    expiry_time = start_time + datetime.timedelta(hours=1)

    blob_client = BlobServiceClient(
        account_url=settings.STORAGE_ACCOUNT_URL,
        credential=settings.STORAGE_ACCESS_KEY,
    )

    sas_token = generate_container_sas(
        account_name=blob_client.account_name,
        container_name=settings.STORAGE_CONTAINER_NAME,
        account_key=blob_client.credential.account_key,
        permission=BlobSasPermissions(read=True, create=True, write=True),
        expiry=expiry_time,
        start=start_time,
    )

    return sas_token
