# %%
from logging import config

import yaml
import asyncio

from src.liquidator import Liquidator


with open("main_logger_config.yml", encoding='UTF-8') as f:
    y = yaml.safe_load(f.read())
    config.dictConfig(y)


if __name__ == '__main__':
    liquidator = Liquidator()
    asyncio.run(liquidator.main())
