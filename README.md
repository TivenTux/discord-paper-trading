### Discord paper trading bot
Simple trading game that allows for LONG or SHORT positions on crypto and the stock market.

Please make a discord bot and get its token here: https://discord.com/developers/applications

![](https://github.com/TivenTux/discord-paper-trading/blob/main/demo.gif)

Docker image is available for download on
**[Dockerhub](https://hub.docker.com/repository/docker/tiventux/discord-paper-trading)**.

## Environment Variables

**discord_token** - your discord bot token(https://discord.com/developers/applications). <br> 
**daily_usd_claim** - Daily user bonus. Enable with 1 disable with 0. Default enabled.  <br>
**daily_usd_amount** - Amount of daily bonus. Defaults to 250$ <br> 

You can specify these environment variables when starting the container using the `-e` command-line option as documented
[here](https://docs.docker.com/engine/reference/run/#env-environment-variables):
```bash
docker run -e "discord_token=yyyyyy"
```
_Privileged Gateway Intents will need to be enabled on Bot options on [discord developers panel](https://discord.com/developers/applications) in order for the command messages to work._

## Running the pre-built docker image

If you just want to run the pre-built docker image, you can run
```bash
docker run --name=discord-paper-trading -d -e "discord_token=yyyyy" tiventux/discord-paper-trading:latest
```

## Building the container

After having cloned this repository, you can run
```bash
docker build -t discord-paper-trading .
```

## Running the container

```bash
docker run -d -e "discord_token=yyyyy" discord-paper-trading

```

_commands:_ 
```.gibs Daily USDT bonus.
.calls View your positions and stats.
.open <TICKER> LONG/SHORT open a trade
.close <slotNumber> closes the trade and realizes profits.
.delete <slotNumber> closes trade and clears slot.
.calls <USER> View stats of another user
```
