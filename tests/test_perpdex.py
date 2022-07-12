import os
import pytest

from src.liquidator import Liquidator
from tests.helper import mock_eth_account


DECIMALS: int = 18


class TestPerpdex:
    @pytest.fixture(autouse=True)
    def setUp(self, mocker):
        self.liq = Liquidator()
        self.exchange = self.liq._perpdex_exchange
        self.my_trader = self.liq._w3.eth.default_account

    def test_deposit(self):
        self.liq._try_transact(
            self.liq._perpdex_exchange.functions.deposit(0),
            options={"value": self.liq._w3.toHex(1), "from": self.my_trader}
        )
