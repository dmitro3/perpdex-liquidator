import os
import pytest

from src.liquidator import Liquidator


class TestLiquidator:
    @pytest.fixture(autouse=True)
    def setUp(self):
        self.liq = Liquidator()

    @pytest.mark.asyncio
    async def test_ok(self):
        trader = '0x46d66016355063aD9A0cAECC2dBdB5E8C5B6C40a'
        base_token = os.environ['BASE_TOKEN_ADDRESS']
        await self.liq._liquidate(trader, base_token)
