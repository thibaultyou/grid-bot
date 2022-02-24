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

Create _.env_ file:

```sh
cd grid-bot
cp .env.sample .env
```

Edit _.env_ file:

```sh
nano .env
```

Adjust settings to your needs, add 4 different API keys with secrets to allow credentials rotations (all the variables are needed):

```ts
MARKET=XXX-PERP
BASE_ORDER_SIZE=25
BUYING_RATIO=1
SELLING_RATIO=1.04
GRID_SIZE=24
GRID_STEP=0.5
FTX_SUBACCOUNT=YOUR_FTX_SUBACCOUNT_NAME
FTX_KEY_1=YOUR_SUBACCCOUNT_FTX_KEY_1
FTX_SECRET_1=YOUR_SUBACCCOUNT_FTX_SECRET_1
FTX_KEY_2=YOUR_SUBACCCOUNT_FTX_KEY_2
FTX_SECRET_2=YOUR_SUBACCCOUNT_FTX_SECRET_2
FTX_KEY_3=YOUR_SUBACCCOUNT_FTX_KEY_3
FTX_SECRET_3=YOUR_SUBACCCOUNT_FTX_SECRET_3
FTX_KEY_4=YOUR_SUBACCCOUNT_FTX_KEY_4
FTX_SECRET_4=YOUR_SUBACCCOUNT_FTX_SECRET_4
```

> Right now only futures are supported by this tool

Run:

```sh
sudo docker-compose up --build -d
```

> To update your config later, edit the config file again and restart the grid bot with the command above

Monitor:

```sh
tail -f ./logs/<MARKET>.log
```
