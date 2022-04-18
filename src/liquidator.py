import asyncio
import json
import os
from logging import getLogger

import web3
from eth_account import Account
from web3 import Web3
from web3.middleware import (construct_sign_and_send_raw_middleware,
                             geth_poa_middleware)

from src.event_indexer import ClearingHouseEventIndexer


class Liquidator:
    def __init__(self, logger=None) -> None:
        self._logger = getLogger(self.__class__.__name__) if logger is None else logger

        self._w3 = get_w3(
            network_name=os.environ['WEB3_NETWORK_NAME'],
            web3_provider_uri=os.environ['WEB3_PROVIDER_URI']
        )
        self._user_account = Account().from_key(os.environ['USER_PRIVATE_KEY'])
        self._w3.middleware_onion.add(construct_sign_and_send_raw_middleware(self._user_account))

        self._clearing_house = get_clearing_house_contract(self._w3)
        self._clearing_house_event_indexer = ClearingHouseEventIndexer(
            contract=self._clearing_house
        )

        self._gas_price = os.environ['GAS_PRICE']

    async def main(self):
        self._logger.info('Start liquidator')
        while True:
            base_token_to_traders = self._clearing_house_event_indexer.fetch_base_token_to_traders()
            await asyncio.gather(*[
                self._liquidate(trader, base_token)
                for base_token, traders in base_token_to_traders.items() for trader in traders
            ])

    async def _liquidate(self, trader, base_token):
        # cancel orders
        func = self._clearing_house.functions.cancelAllExcessOrders(trader, base_token)
        if self._is_executable(func):
            self._try_transact(func, options={'from': self._user_account.address, 'gasPrice': self._gas_price})
        else:
            self._logger.debug(f'Skip cancelAllExcessOrders. {trader=}, {base_token=}')

        # liquidate
        func = self._clearing_house.functions.liquidate(trader, base_token, 0)
        if self._is_executable(func):
            self._try_transact(func, options={'from': self._user_account.address, 'gasPrice': self._gas_price})
        else:
            self._logger.debug(f'Skip liquidate. {trader=}, {base_token=}')

    def _is_executable(self, func):
        try:
            func.estimateGas()
        except Exception as e:
            self._logger.debug(f'estimateGas raises {e=}')
            return False
        return True

    def _try_transact(self, func, options: dict = {}):
        try:
            tx_hash = func.transact(options)
        except web3.exceptions.ContractLogicError as e:
            self._logger.debug(f'transaction reverted. {e=}')
            return False

        if self._wait_transaction_receipt(tx_hash, times=10):
            return True

    def _wait_transaction_receipt(self, tx_hash, times):
        # TODO: not tested yet
        self.logger.info(f"tx_hash:{self._w3.toHex(tx_hash)}")
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


def get_abi_from_file(filepath: str):
    with open(filepath) as f:
        ret = json.load(f)
    return ret['abi']


def get_w3(network_name, web3_provider_uri):
    w3 = Web3(Web3.HTTPProvider(web3_provider_uri))

    if network_name in ['mumbai']:
        w3.middleware_onion.inject(geth_poa_middleware, layer=0)

    return w3


def get_clearing_house_contract(w3):
    contract = w3.eth.contract(
        address=os.environ['CLEARING_HOUSE_PERPDEX_CONTRACT_ADDRESS'],
        abi=get_abi_from_file(os.environ['CLEARING_HOUSE_PERPDEX_CONTRACT_ABI_JSON_FILENAME'])
    )

    return contract
