import os
import pickle
from collections import defaultdict
from logging import getLogger
from types import SimpleNamespace

import web3
from redis_namespace import StrictRedis
from web3._utils.events import get_event_data
from web3.exceptions import MismatchedABI


class EventIndexer:
    def __init__(
        self,
        contract: web3.contract.Contract,
        redis_client=None,
        start_block_number: int = None,
        get_logs_limit: int = None,
        logger=None,
    ) -> None:
        self._contract = contract

        self._redis_client = StrictRedis.from_url(
            os.environ['REDIS_URL'],
            namespace='{}:{}:'.format(os.environ['WEB3_NETWORK_NAME'], self.__class__.__name__),
        ) if redis_client is None else redis_client

        start_block_number = int(
            os.environ['INITIAL_EVENT_BLOCK_NUMBER']) if start_block_number is None else start_block_number
        self._last_block_number = start_block_number - 1
        self._get_logs_limit = 1000 if get_logs_limit is None else get_logs_limit

        self._logger = getLogger(self.__class__.__name__) if logger is None else logger

    def _fetch_events(self):
        # NOTE: use one previous block number to avoid Bad parameter error in get_events call
        current_block = self._contract.web3.eth.block_number - 1
        events = []

        to_block = self._last_block_number
        while to_block < current_block:
            from_block = _floor_int(to_block + 1, self._get_logs_limit, 1)
            to_block = min(from_block + self._get_logs_limit - 1, current_block)
            try:
                es = self._cached_fetch_events(
                    from_block=from_block,
                    to_block=to_block,
                )
                events += es
            except BaseException as exception:
                self._logger.warning(
                    f'error occured while fetching events: {from_block=} {to_block=}, {current_block=}')
                self._logger.warning(f'{exception=}')

        for event in events:
            if self._last_block_number < event['blockNumber']:
                self._process_event(event)

        self._last_block_number = to_block

    def _cached_fetch_events(self, from_block: int, to_block: int):
        cache_enabled = to_block - from_block + 1 == self._get_logs_limit
        if not cache_enabled:
            self._logger.debug(
                'EventIndexer._cached_fetch_events from_block {} to_block {} cache disabled'.format(from_block,
                                                                                                    to_block))
            return get_events(
                self._contract,
                from_block=from_block,
                to_block=to_block,
                logger=self._logger,
            )

        key = 'event_indexer:{}:{}'.format(from_block, to_block)
        value = self._redis_client.get(key)
        if value is None:
            self._logger.debug(
                'EventIndexer._cached_fetch_events from_block {} to_block {} cache miss'.format(from_block, to_block))
            value = get_events(
                self._contract,
                from_block=from_block,
                to_block=to_block,
                logger=self._logger,
            )
            self._redis_client.set(key, pickle.dumps(value))
        else:
            self._logger.debug(
                'EventIndexer._cached_fetch_events from_block {} to_block {} cache hit'.format(from_block, to_block))
            value = pickle.loads(value)

        return value

    def _process_event(self, event: web3.datastructures.AttributeDict):
        raise NotImplementedError


class PerpdexEventIndexer(EventIndexer):
    # - key: market address
    # - value: set of trader address
    market_to_traders = defaultdict(set)

    def fetch_market_to_traders(self):
        self._fetch_events()
        return self.market_to_traders

    def _process_event(self, event: web3.datastructures.AttributeDict):
        event_name = event['event']
        args = event['args']
        self._logger.debug(f'{event_name=} {args=}')
        if event_name == 'PositionChanged':
            self.market_to_traders[args['market']].add(args['trader'])
        elif event_name == 'AddLiquidity':
            self.market_to_traders[args['market']].add(args['trader'])


def _floor_int(a, b, remainder):
    return ((a - remainder) // b) * b + remainder


def create_null_logger():
    def _null_logger_func(x):
        pass
    return SimpleNamespace(
        debug=_null_logger_func,
        error=_null_logger_func,
        warn=_null_logger_func,
        info=_null_logger_func,
    )


def get_events(contract, from_block, to_block, logger=None):
    logger = create_null_logger() if logger is None else logger
    logger.debug(f'get_events of {contract.address=} {from_block}~{to_block}')

    w3 = contract.web3
    logs = w3.eth.get_logs({
        "fromBlock": from_block,
        "toBlock": to_block,
        "address": contract.address,
        "topics": []
    })

    events = []

    for log in logs:
        for contract_event in contract.events:
            abi = contract_event._get_event_abi()

            try:
                ev = get_event_data(w3.codec, abi, log)
                events.append(ev)
            except MismatchedABI:
                ...

    events.sort(key=lambda x: x['blockNumber'])

    return events
