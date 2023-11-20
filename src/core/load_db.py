import asyncio
import logging.config
from pathlib import Path

from lcacollect_config.load_db import load_production_database

logging.config.fileConfig(Path(__file__).parent.parent / "logging.conf", disable_existing_loggers=False)


if __name__ == "__main__":
    asyncio.run(load_production_database())
