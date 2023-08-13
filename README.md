### Discord paper trading bot
Simple trading game that allows for LONG or SHORT positions on crypto and the stock market.

Please make a discord bot and get its token here: https://discord.com/developers/applications

Vantage or CryptoCompare apis not needed anymore as they have been replaced by pyppeteer and TradingView.

Remember to edit chrome_exec_dir with the location of Google Chrome executable. Chromium works too.

![](https://github.com/TivenTux/discord-paper-trading/blob/main/demo.gif)

_commands:_ 
```.gibs Daily USDT bonus.
.calls View your positions and stats.
.open <TICKER> LONG/SHORT open a trade
.close <slotNumber> closes the trade and realizes profits.
.delete <slotNumber> closes trade and clears slot.
.calls <USER> View stats of another user
```

### pip install
```
pycoingecko, discord, pyppeteer, sqlite3
```

### kernel
some distros might need this for google chrome sandbox support on kernel 
```sh
$ sudo sysctl -w kernel.unprivileged_userns_clone=1
```

### deps
for chrome
```sh
$ sudo apt install gconf-service libasound2 libatk1.0-0 libatk-bridge2.0-0 libc6 libcairo2 libcups2 libdbus-1-3 libexpat1 libfontconfig1 libgcc1 libgconf-2-4 libgdk-pixbuf2.0-0 libglib2.0-0 libgtk-3-0 libnspr4 libpango-1.0-0 libpangocairo-1.0-0 libstdc++6 libx11-6 libx11-xcb1 libxcb1 libxcomposite1 libxcursor1 libxdamage1 libxext6 libxfixes3 libxi6 libxrandr2 libxrender1 libxss1 libxtst6 ca-certificates fonts-liberation libappindicator1 libnss3 lsb-release xdg-utils wget
```


