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

    def test_ok(self):
        self._indexer.fetch_base_token_to_traders()
