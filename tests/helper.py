import os
from eth_account import Account


def mock_eth_account(mocker):
    acct = Account.create('KEYSMASH FJAFJKLDSKF7JKFDJ 1530')
    mocker.patch.dict(os.environ, {'USER_PRIVATE_KEY': '0' * 32})
    mocker.patch.object(Account, 'from_key', return_value=acct)
