# perpdex-liquidator

An liquidator bot program for perpdex.

Supported chain

- zksync2-testnet (zksync testnet)
- shibuya (astar testnet)

## Setup

### 1. create private key for EVM

### 2. create .env including USER_PRIVATE_KEY as following:

```
USER_PRIVATE_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### 3. deposit native token for gas

- zksync2 testnet:
  - get ETH Goerli from below urls
    - https://goerli-faucet.mudit.blog/
    - https://faucets.chain.link/goerli
    - https://goerli-faucet.slock.it/
  - deposit ETH Goerli to zksync2 here: https://portal.zksync.io/bridge
- shibuya faucet: https://docs.astar.network/integration/testnet-faucet

## How to run liquidator

```bash
git submodule update --init --recursive

# run liquidator(zksync2 testnet)
docker-compose run --rm py-zksync2-testnet python main.py

# run liquidator(shibuya)
docker-compose run --rm py-shibuya python main.py
```
