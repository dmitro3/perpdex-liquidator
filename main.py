# %%
import asyncio
from logging import config, getLogger

import fire
import yaml

from src.liquidator import Liquidator

with open("main_logger_config.yml", encoding='UTF-8') as f:
    y = yaml.safe_load(f.read())
    config.dictConfig(y)


async def main(restart):
    logger = getLogger(__name__)
    logger.info('start')

    while True:
        liq = Liquidator()

        liq.start()
        while liq.health_check():
            logger.debug('health check ok')
            await asyncio.sleep(30)

        if not restart:
            break
        logger.warning('Restarting Liquidator bot')

    logger.warning('exit')


class Cli:
    """arbitrage bot for perpdex"""

    def run(self, restart: bool = False):
        """run arbitrage bot"""
        asyncio.run(main(restart))


if __name__ == '__main__':
    fire.Fire(Cli)
