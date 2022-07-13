import json

import web3
from eth_account import Account
from web3 import Web3
from web3.middleware import (construct_sign_and_send_raw_middleware,
                             geth_poa_middleware)

MAX_UINT: int = int(web3.constants.MAX_INT, base=16)


def get_w3(network_name: str, web3_provider_uri: str, user_private_key: str = None):
    w3 = Web3(Web3.HTTPProvider(web3_provider_uri))

    if network_name in ['mumbai']:
        w3.middleware_onion.inject(geth_poa_middleware, layer=0)

    if user_private_key is not None:
        user_account = Account().from_key(user_private_key)
        connect_account(w3, user_account)

    return w3


def connect_account(w3: web3.Web3, account: Account):
    # remove old one
    if w3.middleware_onion.get('contract-signer'):
        w3.middleware_onion.remove('contract-signer')

    # add new one
    w3.eth.default_account = account.address
    w3.middleware_onion.add(
        construct_sign_and_send_raw_middleware(account),
        name='contract-signer',
    )


def get_contract_from_abi_json(w3, filepath: str):
    with open(filepath) as f:
        abi = json.load(f)
    contract = w3.eth.contract(
        address=abi['address'],
        abi=abi['abi'],
    )
    return contract
