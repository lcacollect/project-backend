from aiocache import caches
from lcacollect_config import config


class ProjectSettings(config.Settings):
    STORAGE_ACCOUNT_URL: str
    STORAGE_CONTAINER_NAME: str
    STORAGE_ACCESS_KEY: str
    STORAGE_BASE_PATH: str


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
