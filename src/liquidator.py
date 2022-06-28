import asyncio
import glob
import json
import os
from logging import getLogger

import web3
from eth_account import Account
from web3 import Web3
from web3.middleware import (construct_sign_and_send_raw_middleware,
                             geth_poa_middleware)

from src.event_indexer import PerpdexEventIndexer


class Liquidator:
    def __init__(self, logger=None) -> None:
        self._logger = getLogger(self.__class__.__name__) if logger is None else logger

        self._w3 = get_w3(
            network_name=os.environ['WEB3_NETWORK_NAME'],
            web3_provider_uri=os.environ['WEB3_PROVIDER_URI']
        )
        self._user_account = Account().from_key(os.environ['USER_PRIVATE_KEY'])
        self._w3.middleware_onion.add(construct_sign_and_send_raw_middleware(self._user_account))

        self._perpdex_exchange = get_perpdex_exchange_contract(self._w3)
        self._perpdex_exchange_event_indexer = PerpdexEventIndexer(
            contract=self._perpdex_exchange
        )

        self._gas_price = os.environ['GAS_PRICE']

    async def main(self):
        self._logger.info('Start liquidator')
        while True:
            market_to_traders = self._perpdex_exchange_event_indexer.fetch_market_to_traders()

            for market, traders in market_to_traders.items():
                for trader in traders:
                    asyncio.create_task(self._liquidate(trader, market))

    async def _liquidate(self, trader, market):
        # check mm
        ret = self._check_trader_has_enough_mm(trader)
        if ret:
            self._logger.debug(f"Skip liquidation because trader has enough mm. {trader=}, {market=}")
            return

        # liquidate maker position
        self._liquidate_maker_position(trader, market)
        
        # liquidate taker position
        self._liquidate_taker_position(trader, market)

    def _check_trader_has_enough_mm(self, trader):
        return self._perpdex_exchange.functions.hasEnoughMaintenanceMargin(trader).call()

    def _liquidate_maker_position(self, trader, market) -> bool:
        # liquidity, cumBaseSharePerLiquidityX96, cumQuotePerLiquidityX96
        liquidity, _, _ = self._perpdex_exchange.functions.getMakerInfo(trader, market).call()
        if liquidity > 0:
            func = self._perpdex_exchange.functions.removeLiquidity(dict(
                trader=trader,
                market=market,
                liquidity=liquidity,
                minBase=0,
                minQuote=0,
                deadline=int(web3.constants.MAX_INT, base=16),
            ))
            gas = self._try_estimate_gas(func)
            if gas is None:
                self._logger.debug(f"RemoveLiquidity failed in estimation stage. {trader=}, {market=}")
                return False

            ret = self._try_transact(func, options={'from': self._user_account.address, 'gasPrice': gas})
            if ret:
                self._logger.debug("RemoveLiquidity suceeded.")
                return True
            else:
                self._logger.debug(f"RemoveLiquidity failed. {trader=}, {market=}")
                return False

    def _liquidate_taker_position(self, trader, market):
        base_share = self._perpdex_exchange.functions.getOpenPositionShare(trader, market).call()
        max_trade = self._perpdex_exchange.functions.maxTrade(dict(
            trader=trader,
            market=market,
            caller=self._user_account.address,
            is_base_to_quote=base_share > 0,
            is_exact_input=True,
        )).call()

        # try liquidate
        reduction_rate = 0.8
        amount = max(
            base_share,
            max_trade * reduction_rate,
        )
        func = self._perpdex_exchange.functions.trade(dict(
            trader=trader,
            market=market,
            is_base_to_quote=base_share > 0,
            is_exact_input=True,
            amount=amount,
            oppositeAmountBound=0,
            deadline=int(web3.constants.MAX_INT, base=16),
        ))

        gas = self._try_estimate_gas(func)
        if gas is None:
            return False
        
        ret = self._try_transact(func, options={'from': self._user_account.address, 'gasPrice': gas})
        if ret:
            self._logger.debug(f'Liquidation succeeded. {trader=}, {market=}, {base_share=}, {max_trade=}, {amount=}')
            return True
        else:
            self._logger.debug(f'Liquidation failed. {trader=}, {market=}, {base_share=}, {max_trade=}, {amount=}')
            return False
    
    def _try_estimate_gas(self, func) -> int:
        try:
            return func.estimateGas()
        except Exception as e:
            self._logger.debug(f'estimateGas raises {e=}')
            return
   
    def _try_transact(self, func, options: dict = {}):
        try:
            tx_hash = func.transact(options)
        except web3.exceptions.ContractLogicError as e:
            self._logger.debug(f'transaction reverted. {e=}')
            return False

        if self._wait_transaction_receipt(tx_hash, times=10):
            return True

    def _wait_transaction_receipt(self, tx_hash, times):
        self._logger.info(f"tx_hash:{self._w3.toHex(tx_hash)}")
        for i in range(times):
            try:
                tx_receipt = self._w3.eth.waitForTransactionReceipt(tx_hash, 10)
                self._logger.info(tx_receipt)
                status = tx_receipt['status']
                if status == 0:
                    # transaction failed
                    return False
                elif status == 1:
                    # transaction success
                    return True
            except BaseException as e:
                self._logger.warning('waiting tx failed {} time(s): {}'.format(i, e))
                continue
        return False


def get_w3(network_name, web3_provider_uri):
    w3 = Web3(Web3.HTTPProvider(web3_provider_uri))

    if network_name in ['mumbai']:
        w3.middleware_onion.inject(geth_poa_middleware, layer=0)

    return w3


def get_perpdex_exchange_contract(w3):
    dirpath = os.environ['PERPDEX_ABI_JSON_DIRPATH']
    filepath = os.path.join(dirpath, 'PerpdexExchange.json')
    with open(filepath) as f:
        ret = json.load(f)

    contract = w3.eth.contract(
        address=ret['address'],
        abi=ret['abi'],
    )

    return contract


def get_perpdex_market_addresses(w3):
    dirpath = os.environ['PERPDEX_ABI_JSON_DIRPATH']
    searchpath = os.path.join(dirpath, 'PerpdexMarket*.json')
    addresses = []
    filepaths = []
    for filepath in glob.glob(searchpath):
        with open(filepath) as f:
            ret = json.load(f)
        addresses.append(ret['address'])
        filepaths.append(filepath)
    return addresses, filepaths
