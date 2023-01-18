from typing import Any

from aiocache import caches
from azure.identity import ClientSecretCredential
from lcacollect_config import config
from pydantic import validator


class ProjectSettings(config.Settings):
    ROUTER_URL: str
    # graph
    AAD_GRAPH_SECRET: str
    # sendgrid
    SENDGRID_SECRET: str
    # Email address to send email notifications from
    EMAIL_NOTIFICATION_FROM: str
    # Azure AD
    INTERNAL_EMAIL_DOMAIN_NAMES: str
    INTERNAL_EMAIL_DOMAINS_LIST: list[str] | None = None
    DEFAULT_AD_FQDN: str
    # Azure Graph API
    AAD_GRAPH_CREDENTIAL: ClientSecretCredential | None = None
    # Azure storage
    STORAGE_ACCOUNT_URL: str
    STORAGE_CONTAINER_NAME: str
    STORAGE_ACCESS_KEY: str
    STORAGE_BASE_PATH: str

    @validator("AAD_GRAPH_CREDENTIAL")
    def assemble_graph_credential(
        cls, v: ClientSecretCredential | None, values: dict[str, Any]
    ) -> ClientSecretCredential:
        if isinstance(v, ClientSecretCredential):
            return v
        return ClientSecretCredential(
            tenant_id=values.get("AAD_TENANT_ID"),
            client_id=values.get("AAD_APP_CLIENT_ID"),
            client_secret=values.get("AAD_GRAPH_SECRET"),
        )

    @validator("INTERNAL_EMAIL_DOMAINS_LIST")
    def assemble_email_domains(
        cls,
        v: list[str] | None,
        values: dict[str, str],
    ) -> list[str]:
        if v:
            return v
        return values.get("INTERNAL_EMAIL_DOMAIN_NAMES").split(",")


settings = ProjectSettings()

caches.set_config(
    {
        "default": {
            "cache": "aiocache.SimpleMemoryCache",
            "serializer": {"class": "aiocache.serializers.StringSerializer"},
        },
        "azure_users": {
            "cache": "aiocache.SimpleMemoryCache",
            "serializer": {"class": "aiocache.serializers.PickleSerializer"},
        },
    }
)
