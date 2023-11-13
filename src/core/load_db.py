import asyncio
import logging
import logging.config
import os
from pathlib import Path

import asyncpg
from lcacollect_config.connection import create_postgres_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from core.config import settings

logging.config.fileConfig(Path(__file__).parent.parent / "logging.conf", disable_existing_loggers=False)
logger = logging.getLogger(__name__)


async def main():
    sql_folder = Path("/app/db_backups")
    sql_folder.mkdir(exist_ok=True)
    logger.info(f"Created folder {sql_folder}")

    sql_file = sql_folder / f"{settings.POSTGRES_DB}.sql"
    db_config = {
        "user": os.getenv("AZURE_POSTGRES_USER"),
        "host": os.getenv("AZURE_POSTGRES_HOST"),
        "port": os.getenv("AZURE_POSTGRES_PORT"),
        "database": settings.POSTGRES_DB,
        "password": os.getenv("AZURE_POSTGRES_PASSWORD"),
    }
    await download_latest_db(sql_file, db_config)
    await prepare_db(sql_file)
    await load_latest_db(sql_file)


async def download_latest_db(sql_path: Path, db_config: dict):
    cmd = (
        f"pg_dump -h {db_config.get('host')} -U {db_config.get('user')} "
        f"-p {db_config.get('port')} -d {db_config.get('database')} > {str(sql_path)}"
    )

    logger.info("Starting downloading database")

    process = await asyncio.create_subprocess_shell(
        cmd,
        stderr=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        env={"PGPASSWORD": db_config.get("password")},
    )

    stdout, stderr = await process.communicate()

    logger.info("Finished downloading")
    if stdout:
        logger.info(stdout.decode())
    if stderr:
        logger.error(stderr.decode())


async def load_latest_db(sql_path: Path):
    cmd = (
        f"psql -h {settings.POSTGRES_HOST} -U {settings.POSTGRES_USER} "
        f"-p {settings.POSTGRES_PORT} -d {settings.POSTGRES_DB} -f {str(sql_path)}"
    )

    logger.info("Starting loading database")

    process = await asyncio.create_subprocess_shell(
        cmd,
        stderr=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        env={"PGPASSWORD": settings.POSTGRES_PASSWORD},
    )

    stdout, stderr = await process.communicate()

    logger.info("Loaded database")
    if stdout:
        logger.info(stdout.decode())
    if stderr:
        logger.error(stderr.decode())


async def create_azure_roles(connection):
    logger.info("Creating Azure roles")
    await connection.execute("CREATE ROLE azure_pg_admin")
    await connection.execute("CREATE ROLE lcadbadmin")


async def prepare_db(sql_file: Path):
    logger.info(f"Loading downloaded database: {sql_file}")
    conn = await asyncpg.connect(
        user=settings.POSTGRES_USER,
        database="postgres",
        port=settings.POSTGRES_PORT,
        host=settings.POSTGRES_HOST,
        password=settings.POSTGRES_PASSWORD,
    )
    try:
        logger.info("Established connection to database")
        await conn.execute(
            f"SELECT pg_terminate_backend(pg_stat_activity.pid) FROM pg_stat_activity WHERE pg_stat_activity.datname = '{settings.POSTGRES_DB}' AND pid <> pg_backend_pid()"
        )
        logger.info("Dropping database")
        await conn.execute(f"DROP DATABASE IF EXISTS {settings.POSTGRES_DB}")
        logger.info("Creating new database")
        await conn.execute(f"CREATE DATABASE {settings.POSTGRES_DB}")
        logger.info("Closed connection to database")
        await create_azure_roles(conn)

    except Exception as e:
        logger.error(e)
        raise e
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
