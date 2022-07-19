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

    def test_cache_disabled(self, mocker):
        from_block = 0
        to_block = from_block + 10

        mocked = mocker.patch('src.event_indexer.get_events', return_value=[])

        n = 10
        for _ in range(n):
            self._indexer._cached_fetch_events(from_block, to_block)
        assert mocked.call_count == n

    def test_cache_hit(self, mocker):
        from_block = 0
        to_block = from_block + 1000 - 1

        mocked = mocker.patch('src.event_indexer.get_events', return_value=[])

        n = 10
        for _ in range(n):
            self._indexer._cached_fetch_events(from_block, to_block)
        assert mocked.call_count == 1

    def test_process_event(self, mocker):
        event1 = {'event': 'PositionChanged', 'args': {'market': '0x1234-1', 'trader': '0xabcd-1'}}
        event2 = {'event': 'NotTargetEvent', 'args': {'market': '0x1234-2', 'trader': '0xabcd-2'}}
        for event in [event1, event2]:
            self._indexer._process_event(event)

        assert event1['args']['market'] in self._indexer.market_to_traders
        assert event1['args']['trader'] in self._indexer.market_to_traders[event1['args']['market']]

        assert event2['args']['market'] not in self._indexer.market_to_traders

    def test_smoke(self):
        self._indexer.fetch_market_to_traders()
