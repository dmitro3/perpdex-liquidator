import os
import pytest

from src.liquidator import Liquidator
from tests.helper import mock_eth_account


class TestLiquidator:
    @pytest.fixture(autouse=True)
    def setUp(self, mocker):
        # mock Account
        mock_eth_account(mocker)

        self.liq = Liquidator()

    @pytest.mark.asyncio
    async def test_ok(self):
        trader = '0x46d66016355063aD9A0cAECC2dBdB5E8C5B6C40a'
        base_token = os.environ['BASE_TOKEN_ADDRESS']
        await self.liq._liquidate(trader, base_token)
