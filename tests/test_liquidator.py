import pytest
from src.liquidator import Liquidator
from web3.exceptions import ContractLogicError

from tests.helper import mock_eth_account


class TestLiquidator:
    @pytest.fixture(autouse=True)
    def setUp(self, mocker):
        # mock Account
        mock_eth_account(mocker)

        self.liq = Liquidator()
        self.trader = 'trader address'
        self.market = 'base token address'
    
    @pytest.mark.asyncio
    async def test_liquidate_skip(self, mocker):
        mocker.patch.object(self.liq, '_check_trader_has_enough_mm', return_value=True)
        mocker.patch.object(self.liq, '_liquidate_maker_position')
        mocker.patch.object(self.liq, '_liquidate_taker_position')

        await self.liq._liquidate(self.trader, self.market)

        self.liq._liquidate_maker_position.assert_not_called()
        self.liq._liquidate_taker_position.assert_not_called()

    @pytest.mark.asyncio
    async def test_liquidate_executed(self, mocker):
        mocker.patch.object(self.liq, '_check_trader_has_enough_mm', return_value=False)
        mocker.patch.object(self.liq, '_liquidate_maker_position')
        mocker.patch.object(self.liq, '_liquidate_taker_position')

        await self.liq._liquidate(self.trader, self.market)

        self.liq._liquidate_maker_position.assert_called()
        self.liq._liquidate_taker_position.assert_called()
    
    def test_liquidate_maker_position_ok(self, mocker):
        contract = self.liq._perpdex_exchange.functions

        # mock getMakerInfo to return liquidity 10
        func1 = mocker.MagicMock()
        func1.call.return_value = (10, 0, 0)
        mocker.patch.object(contract, 'getMakerInfo', return_value=func1)

        # mock removeLiquidity
        func2 = mocker.MagicMock()
        func2.estimateGas.return_value = 100
        mocker.patch.object(contract, 'removeLiquidity', return_value=func2)

        # mock transact to return True
        mocker.patch.object(self.liq, '_try_transact', return_value=True)

        ret = self.liq._liquidate_maker_position(self.trader, self.market)
        assert ret is True

    def test_liquidate_taker_position_ok(self, mocker):
        contract = self.liq._perpdex_exchange.functions

        # mock getOpenPositionShare
        func1 = mocker.MagicMock()
        func1.call.return_value = 100
        mocker.patch.object(contract, 'getOpenPositionShare', return_value=func1)

        # mock maxTrade
        func2 = mocker.MagicMock()
        func2.call.return_value = 80
        mocker.patch.object(contract, 'maxTrade', return_value=func2)

        # mock trade
        func3 = mocker.MagicMock()
        func3.estimateGas.return_value = 100
        mocker.patch.object(contract, 'trade', return_value=func3)

        # mock transact to return True
        mocker.patch.object(self.liq, '_try_transact', return_value=True)

        ret = self.liq._liquidate_taker_position(self.trader, self.market)
        assert ret is True
