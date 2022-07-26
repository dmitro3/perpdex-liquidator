# perpdex-liquidator

An liquidator bot program for perpdex.

Supported chain

- shibuya (astar testnet)
- zksync2-testnet (zksync testnet)

## Setup

see: https://github.com/perpdex/perpdex-arbitrager#setup

## How to run liquidator
```bash
git submodule update --init --recursive

# run liquidator(shibuya)
docker-compose run --rm py-shibuya python main.py

# run liquidator(zksync2 testnet)
docker-compose run --rm py-zksync2-testnet python main.py
```
