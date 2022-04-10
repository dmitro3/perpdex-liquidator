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
        self.base_token = 'base token address'

    def test_is_executable_ok(self, mocker):
        mocked_func = mocker.MagicMock()
        mocker.patch.object(
            mocked_func,
            'estimateGas',
            return_value=10000)
        assert self.liq._is_executable(mocked_func) is True

    def test_is_executable_ng(self, mocker):
        mocked_func = mocker.MagicMock()
        mocker.patch.object(
            mocked_func,
            'estimateGas',
            side_effect=ContractLogicError('execution reverted'))
        assert self.liq._is_executable(mocked_func) is False

    @pytest.mark.asyncio
    async def test_liquidate_executed(self, mocker):
        # mock _try_transact
        mocker.patch.object(self.liq, '_try_transact')

        # mock cancelAllExcessOrders estimateGas to return gas
        mocked_clearing_house = mocker.patch.object(self.liq, '_clearing_house')
        mocked_cancelAllExcessOrders_func = mocker.MagicMock()
        mocker.patch.object(
            mocked_clearing_house.functions,
            'cancelAllExcessOrders',
            return_value=mocked_cancelAllExcessOrders_func)
        mocker.patch.object(
            mocked_cancelAllExcessOrders_func,
            'estimateGas',
            return_value=10000)

        # mock liquidate estimateGas to return gas
        mocked_liquidate_func = mocker.MagicMock()
        mocker.patch.object(
            mocked_clearing_house.functions,
            'liquidate',
            return_value=mocked_liquidate_func)
        mocker.patch.object(
            mocked_liquidate_func,
            'estimateGas',
            return_value=10000)

        await self.liq._liquidate(self.trader, self.base_token)

        # assert liquidate transact called
        self.liq._try_transact.assert_called_with(
            mocked_liquidate_func,
            options={'from': self.liq._user_account.address, 'gasPrice': self.liq._gas_price}
        )

    @pytest.mark.asyncio
    async def test_liquidate_skiped(self, mocker):
        # mock _try_transact
        mocker.patch.object(self.liq, '_try_transact')

        # mock cancelAllExcessOrders estimateGas to raise revert error
        mocked_clearing_house = mocker.patch.object(self.liq, '_clearing_house')
        mocked_cancelAllExcessOrders_func = mocker.MagicMock()
        mocker.patch.object(
            mocked_clearing_house.functions,
            'cancelAllExcessOrders',
            return_value=mocked_cancelAllExcessOrders_func)
        mocker.patch.object(
            mocked_cancelAllExcessOrders_func,
            'estimateGas',
            side_effect=ContractLogicError('execution reverted: CH_NEXO'))

        # mock liquidate estimateGas to raise revert error
        mocked_liquidate_func = mocker.MagicMock()
        mocker.patch.object(
            mocked_clearing_house.functions,
            'liquidate',
            return_value=mocked_liquidate_func)
        mocker.patch.object(
            mocked_liquidate_func,
            'estimateGas',
            side_effect=ContractLogicError('execution reverted'))

        await self.liq._liquidate(self.trader, self.base_token)

        # assert liquidate transact not called
        assert self.liq._try_transact.call_count == 0
