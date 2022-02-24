# FTX grid bot

## Install

Refresh apt and update definitions:

```sh
    sudo apt update -y
    sudo apt upgrade -y
```

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
MARKET=ADA-PERP
BASE_ORDER_SIZE=20
BUYING_RATIO=1
SELLING_RATIO=1.05
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

Run:

```sh
    sudo docker-compose up --build -d
```

Monitor:

```sh
    tail -f ./logs/<MARKET>.log
```
