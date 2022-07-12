import os
from logging import config

import pytest
import yaml
from src.event_indexer import PerpdexEventIndexer
from src.liquidator import get_perpdex_exchange_contract, get_w3

with open("main_logger_config.yml", encoding='UTF-8') as f:
    y = yaml.safe_load(f.read())
    config.dictConfig(y)


class TestPerpdexEventIndexer:
    @pytest.fixture(autouse=True)
    def setUp(self):
        w3 = get_w3(
            network_name=os.environ['WEB3_NETWORK_NAME'],
            web3_provider_uri=os.environ['WEB3_PROVIDER_URI']
        )
        self._indexer = PerpdexEventIndexer(
            contract=get_perpdex_exchange_contract(w3),
        )
        self._indexer._redis_client.flushdb()

    def test_ok(self):
        self._indexer.fetch_market_to_traders()
