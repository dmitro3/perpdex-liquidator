import os
import pytest

from src.event_indexer import ClearingHouseEventIndexer
from src.liquidator import get_clearing_house_contract, get_w3


class TestClearingHouseEventIndexer:
    @pytest.fixture(autouse=True)
    def setUp(self):
        w3 = get_w3(
            network_name=os.environ['WEB3_NETWORK_NAME'],
            web3_provider_uri=os.environ['WEB3_PROVIDER_URI']
        )
        self._indexer = ClearingHouseEventIndexer(
            contract=get_clearing_house_contract(w3),
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
        event1 = {'event': 'LiquidityChanged', 'args': {'baseToken': '0x1234-0', 'maker': '0xabcd-0'}}
        event2 = {'event': 'PositionChanged', 'args': {'baseToken': '0x1234-1', 'taker': '0xabcd-1'}}
        event3 = {'event': 'NotTargetEvent', 'args': {'baseToken': '0x1234-2', 'taker': '0xabcd-2'}}
        for event in [event1, event2, event3]:
            self._indexer._process_event(event)

        assert event1['args']['baseToken'] in self._indexer.base_token_to_traders
        assert event1['args']['maker'] in self._indexer.base_token_to_traders[event1['args']['baseToken']]

        assert event2['args']['baseToken'] in self._indexer.base_token_to_traders
        assert event2['args']['taker'] in self._indexer.base_token_to_traders[event2['args']['baseToken']]

        assert event3['args']['baseToken'] not in self._indexer.base_token_to_traders
