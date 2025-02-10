import asyncio
from datetime import datetime
import logging

import pytz
from py_tools.connections.db.mysql import DBManager, BaseOrmTable, SQLAlchemyManager
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from bot.bot_client import BotClient
from bot.commands import CommandHandler
from config import config
from core.emby_api import EmbyApi, EmbyRouterAPI
from services import UserService

# Initialize logger
logger = logging.getLogger(__name__)


async def main():

    def _init_logger():
        logging.basicConfig(
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            level=config.log_level,
            filename="default.log",
        )

    _init_logger()

    async def create_database_if_not_exists():
        # 创建一个不指定数据库名称的引擎
        engine_without_db = create_async_engine(
            f"mysql+asyncmy://{config.db_user}:{config.db_pass}@{config.db_host}:{config.db_port}/",
            echo=True,
        )
        async with engine_without_db.begin() as conn:
            # 执行创建数据库的语句
            query = f"CREATE DATABASE IF NOT EXISTS {config.db_name}"
            logger.info(f"SQL Query: {query}, Context: Creating database")
            await conn.execute(text(query))
        await engine_without_db.dispose()

    # 创建数据库
    async def _init_db():
        await create_database_if_not_exists()

        db_client = SQLAlchemyManager(
            host=config.db_host,
            port=config.db_port,
            user=config.db_user,
            password=config.db_pass,
            db_name=config.db_name,
        )
        db_client.init_mysql_engine()
        DBManager.init_db_client(db_client)
        async with DBManager.connection() as conn:
            query = str(BaseOrmTable.metadata.create_all(bind=conn.engine))
            logger.info(f"SQL Query: {query}, Context: Creating tables")
            await conn.run_sync(BaseOrmTable.metadata.create_all)



    def _init_tz():
        if config.timezone:
            pytz.timezone(config.timezone)
            logger.info(f"Timezone: {config.timezone}")

    logger.info(datetime.now())
    _init_tz()
    # _init_logger()
    await _init_db()

    # 创建Bot客户端
    bot_client = BotClient(
        api_id=config.api_id,
        api_hash=config.api_hash,
        bot_token=config.bot_token,
        name="emby_bot",
    )
    emby_api = EmbyApi(config.emby_url, config.emby_api)
    emby_router_api = EmbyRouterAPI(config.api_url, config.api_key)
    # 设置命令处理
    command_handler = CommandHandler(
        bot_client=bot_client,
        user_service=UserService(
            emby_api=emby_api,
            emby_router_api=emby_router_api
        )
    )

    try:
        await bot_client.start()
        await asyncio.sleep(1)
        # ✅ 获取群组成员
        members_in_group = await bot_client.get_group_members(config.telegram_group_ids)
        for group_members in members_in_group.values():
            for telegram_id in group_members:
                config.group_members[telegram_id] = group_members[telegram_id]

        command_handler.setup_commands()
        await bot_client.idle()

    except Exception as e:
        logger.error(f"Failed to start bot: {e}", exc_info=True)
        await bot_client.stop()
        return


if __name__ == "__main__":
    asyncio.run(main())
    logger.info("bot stop")
    # _init_logger()
    # logging.info("Bot is running...")
    # _init_db()
    # loop = asyncio.get_event_loop()
    # loop.run_until_complete(main())
