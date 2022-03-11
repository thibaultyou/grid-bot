# FTX grid bot

A dynamic grid bot implementation using limit orders to trade futures on [FTX](https://ftx.com/referrals#a=5513581) cryptocurrency exchange.

⚠️⚠️⚠️ This project is under construction, expect to encounter problems or strange behavior.

Trading is very risky, neither the developer nor the contributors can be held responsible for your actions.

Beware of the fees associated with trading on FTX, a small grid size or currencies with high slippage could kill your account balance quickly.

Please understand your risk before running this tool
⚠️⚠️⚠️

## Install

Refresh apt definitions and update:

```sh
sudo apt update -y
sudo apt upgrade -y
```

> You may need to reboot your instance after updating

Clone repo:

```sh
git clone git@github.com:thibaultyou/grid-bot.git
```

Install Docker:

```sh
sudo apt install docker.io -y
sudo apt install docker-compose -y
```

## Usage

Create _.env.btc_ env file for BTC (as example):

```sh
cd grid-bot
cp .env.sample .env.btc
```

Edit _.env.btc_ file:

```sh
nano .env.btc
```

Adjust settings to your needs like the following example, add 4 different API keys with secrets to allow credentials rotations (all the variables are needed):

```ts
MARKET=BTC-PERP
BASE_ORDER_SIZE=10
BUYING_RATIO=1
SELLING_RATIO=1.1
GRID_SIZE=5
GRID_STEP=1
FTX_SUBACCOUNT=BTC
FTX_KEY_1=kEy_1
FTX_SECRET_1=SeCrEt_1
FTX_KEY_2=kEy_2
FTX_SECRET_2=SeCrEt_2
FTX_KEY_3=kEy_3
FTX_SECRET_3=SeCrEt_3
FTX_KEY_4=kEy_4
FTX_SECRET_4=SeCrEt_4
```

Edit _docker-compose.yml_ file:

```sh
nano docker-compose.yml
```

Adjust to your needs, for example two grids here with BTC and XRP (don't forget to create corresponding env files):

```yml
version: '3'
services:
  btc:
    build: .
    restart: unless-stopped
    volumes:
      - ./logs:/code/logs
      - ./.env.btc:/code/.env # you need this to bind your env file to this grid instance

  # you can add as many instance you want as long you have different API keys between each and enough RAM on your server
  xrp:
    build: .
    restart: unless-stopped
    volumes:
      - ./logs:/code/logs
      - ./.env.xrp:/code/.env
```

> Right now only futures are supported by this tool

Run:

```sh
sudo docker-compose up --build -d
```

If you have issues updating your config you can recreate the instances:

```sh
sudo docker-compose stop
sudo docker-compose rm
sudo docker-compose up --build -d
```

Monitor:

```sh
tail -f ./logs/<MARKET>.log
```
