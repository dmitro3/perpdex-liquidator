import pytest

from src.liquidator import Liquidator, get_perpdex_market_address
from tests.helper import mock_eth_account


class TestLiquidator:
    @pytest.fixture(autouse=True)
    def setUp(self, mocker):
        # mock Account
        mock_eth_account(mocker)

        self.liq = Liquidator()
        self.market = get_perpdex_market_address(self.liq._w3, 'PerpdexMarketETH.json')

    @pytest.mark.asyncio
    async def test_liquidate_skiped(self):
        trader = '0x' + '0' * 40
        await self.liq._liquidate(trader, self.market)
