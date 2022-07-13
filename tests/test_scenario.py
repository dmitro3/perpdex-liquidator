import time
import asyncio
import os
from logging import config

import pytest
import yaml
from eth_account import Account
from src.liquidator import Liquidator
from src.contracts import utils

with open("main_logger_config.yml", encoding='UTF-8') as f:
    y = yaml.safe_load(f.read())
    config.dictConfig(y)


Q96: int = 0x1000000000000000000000000  # same as 1 << 96
DECIMALS: int = 18

HARDHAT_PRIVATE_KEY0 = '0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80'
HARDHAT_PRIVATE_KEY1 = '0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d'


@pytest.fixture
def w3():
    if os.environ['WEB3_NETWORK_NAME'] not in ('localhost'):
        raise ValueError("Warning: probably wrong environment variables")

    return utils.get_w3(
        network_name=os.environ['WEB3_NETWORK_NAME'],
        web3_provider_uri=os.environ['WEB3_PROVIDER_URI'],
        user_private_key=os.environ['USER_PRIVATE_KEY'],
    )


@pytest.fixture
def market_filepath():
    return os.path.join(
        os.environ['PERPDEX_CONTRACT_ABI_JSON_DIRPATH'], 'PerpdexMarketBTC.json')


@pytest.fixture
def market_contract(w3, market_filepath):
    return utils.get_contract_from_abi_json(w3, market_filepath)


@pytest.fixture
def exchange_filepath():
    return os.path.join(
        os.environ['PERPDEX_CONTRACT_ABI_JSON_DIRPATH'], 'PerpdexExchange.json')


@pytest.fixture
def exchange_contract(w3, exchange_filepath):
    return utils.get_contract_from_abi_json(w3, exchange_filepath)


@pytest.fixture(autouse=True, scope='function')
def before_after(w3, market_contract, exchange_contract):
    yield

    # teardown

    # reset pool info
    tx = market_contract.functions.setPoolInfo(dict(
        base=0,
        quote=0,
        totalLiquidity=0,
        cumBasePerLiquidityX96=0,
        cumQuotePerLiquidityX96=0,
        baseBalancePerShareX96=0,
    )).transact()
    w3.eth.wait_for_transaction_receipt(tx)

    # reset account info
    tx = exchange_contract.functions.setAccountInfo(
        w3.eth.default_account,     # trader
        dict(collateralBalance=0),  # vaultInfo
        [],                         # markets
    ).transact()
    w3.eth.wait_for_transaction_receipt(tx)

    # reset taker info
    tx = exchange_contract.functions.setTakerInfo(
        w3.eth.default_account,                    # trader
        market_contract.address,                   # market
        dict(baseBalanceShare=0, quoteBalance=0),  # takerInfo
    ).transact()
    w3.eth.wait_for_transaction_receipt(tx)

    # reset maker info
    tx = exchange_contract.functions.setMakerInfo(
        w3.eth.default_account,                    # trader
        market_contract.address,                   # market
        dict(liquidity=0, cumBaseSharePerLiquidityX96=0, cumQuotePerLiquidityX96=0),  # makerInfo
    ).transact()
    w3.eth.wait_for_transaction_receipt(tx)

    # reset insurance fund info
    tx = exchange_contract.functions.setInsuranceFundInfo(
        dict(balance=0, liquidationRewardBalance=0)  # InsuranceFundInfo
    ).transact()
    w3.eth.wait_for_transaction_receipt(tx)

    # reset protocol info
    tx = exchange_contract.functions.setProtocolInfo(
        dict(protocolFee=0)  # ProtocolInfo
    ).transact()
    w3.eth.wait_for_transaction_receipt(tx)


@pytest.mark.asyncio
async def test_liquidate_no_pos():
    liq = Liquidator()
    liq.start()

    assert liq.health_check() is True

    # force revert the running task
    liq._task.cancel()
    try:
        await liq._task
    except asyncio.CancelledError:
        pass
    assert liq.health_check() is False


@pytest.mark.asyncio
async def test_liquidate(w3, market_contract, exchange_contract):
    owner = Account().from_key(HARDHAT_PRIVATE_KEY0)
    alice = Account().from_key(HARDHAT_PRIVATE_KEY1)

    # make alice collateral 10000 quote
    utils.connect_account(w3, owner)
    _set_trader_collateral(w3, exchange_contract, alice.address, 10000)

    # mark price is now 100
    _set_mark_price(w3, market_contract, 100)

    # alice adds liquidity
    utils.connect_account(w3, alice)
    tx_hash = exchange_contract.functions.addLiquidity(dict(
        market=market_contract.address,
        base=int(0.1 * (10 ** DECIMALS)),
        quote=int(0.1 * 100 * (10 ** DECIMALS)),
        minBase=0,
        minQuote=0,
        deadline=utils.MAX_UINT,
    )).transact()
    w3.eth.wait_for_transaction_receipt(tx_hash)

    # alice opens long position
    side_int = 1
    size = 1.0

    amount = int(size * (10 ** DECIMALS))

    utils.connect_account(w3, alice)
    tx_hash = exchange_contract.functions.trade(dict(
        trader=alice.address,
        market=market_contract.address,
        isBaseToQuote=(side_int < 0),
        isExactInput=(side_int < 0),  # same as isBaseToQuote
        amount=amount,
        oppositeAmountBound=0 if (side_int < 0) else utils.MAX_UINT,
        deadline=utils.MAX_UINT,
    )).transact({'gasPrice': 1_000_000})
    w3.eth.wait_for_transaction_receipt(tx_hash)

    # alice mm becomes not enough
    utils.connect_account(w3, owner)
    _set_trader_collateral(w3, exchange_contract, alice.address, -1.0)

    pos = _current_position(w3, market_contract, exchange_contract, alice.address)
    assert pos > 0

    # assert liquidation success
    liq = Liquidator()
    await liq._liquidate(alice.address, market_contract.address)

    pos = _current_position(w3, market_contract, exchange_contract, alice.address)
    assert pos == 0.0

    maker_info = _current_maker_info(w3, market_contract, exchange_contract, alice.address)
    assert maker_info['liquidity'] == 0


# change mark price to 100.0 (quote/base*baseBalancePerShare)
def _set_mark_price(_w3, _market_contract, mp):
    tx_hash = _market_contract.functions.setPoolInfo(dict(
        base=int(1000 * 10 ** DECIMALS),
        quote=int(1000 * mp * 10 ** DECIMALS),
        totalLiquidity=100000,
        cumBasePerLiquidityX96=0,
        cumQuotePerLiquidityX96=0,
        baseBalancePerShareX96=1 * Q96,
    )).transact()
    _w3.eth.wait_for_transaction_receipt(tx_hash)


def _set_trader_collateral(_w3, _exchange_contract, trader_address, col):
    # mock collateral
    tx_hash = _exchange_contract.functions.setAccountInfo(
        trader_address,                                       # trader
        dict(collateralBalance=int(col * (10 ** DECIMALS))),  # vaultInfo
        [],                                                   # markets
    ).transact()
    _w3.eth.wait_for_transaction_receipt(tx_hash)


def _current_position(_w3, _market_contract, _exchange_contract, trader_address) -> float:
    base_share = _exchange_contract.functions.getPositionShare(
        trader_address,
        _market_contract.address,
    ).call()
    return base_share / (10 ** DECIMALS)


def _current_maker_info(_w3, _market_contract, _exchange_contract, trader_address) -> dict:
    ret = _exchange_contract.functions.getMakerInfo(trader_address, _market_contract.address).call()
    return dict(
        liquidity=ret[0],
        cumBaseSharePerLiquidityX96=ret[1],
        cumQuotePerLiquidityX96=ret[2],
    )
