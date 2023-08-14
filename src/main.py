import requests, time, json, asyncio 
import os
from os import environ
import discord, sqlite3
from pyppeteer import launch
from pycoingecko import CoinGeckoAPI
cg = CoinGeckoAPI()

#discord_bot_token
discord_token = os.environ['discord_token']

client = discord.Client(prefix='', intents=discord.Intents().all())

#daily usd bonus for each player. 1 to enable 0 to disable
#check if ENV vars are set otherwise use defaults
daily_usd_claim = 1
daily_usd_amount = 250
if environ.get('daily_usd_claim') is not None:
    daily_usd_claim = int(os.environ['daily_usd_claim'])
else:
    daily_usd_claim = 1
if environ.get('daily_usd_amount') is not None:
    daily_usd_amount = int(os.environ['daily_usd_amount'])
else:
    daily_usd_claim = 250

#tv base url
tvbase = base1symbol = 'https://www.tradingview.com/widgetembed/?frameElementId=tradingview_e1816&symbol='
#these have to be updated on tradingview layout changes
tv_css_vol = 'div.valueValue-l31H9iuA:nth-child(1)'
tv_css_closeprice = 'div.valuesWrapper-l31H9iuA > div > div:nth-child(5) > div.valueValue-l31H9iuA'

#where chrome executable is located
chrome_exec_dir = '/usr/bin/google-chrome'
#browser arguments
chrome_exec_args = ["--proxy-server='direct://'", '--proxy-bypass-list=*', '--user-data-dir=./tmp']
#main database file location
database = './calls.db'

#not used anymore - cryptocompare api - replaced by gecko and tv
crypto_compare_token = os.environ['crypto_compare_token']

### conf end
###
#refreshing coins list
dump1 = cg.get_coins_list()
print('caching coins list')

#win loss ratio calculation - for user stats
def ratioFunction(num1, num2):
    '''
    Takes number1 and number2, returns w/l ratio.'''
    try:
        if int(num1) >= 1 and int(num2) == 0:
            result = '{0:.2f}'.format(float(num1))
        else:
            ratio12 = float(num1/num2)
            print('The ratio of', str(num1), 'and', str(num2),'is', str(ratio12) + '.')
            result = '{0:.2f}'.format(float(ratio12))
    except Exception as e:
        print(e)
        result = '-'
    return str(result)

#calculate percentage
def get_change(previous, current):
    '''
    Takes first and second number, returns the change in percent.
    '''
    #if current == previous:
    #    return 100.0
    try:
        roso = (abs(float(current) - float(previous)) / float(previous)) * 100.0
        rosod = "%.3f" % roso
        return rosod
    except ZeroDivisionError:
        return 0

#if all APIs fail, use chrome and scrape tv for price data
async def tradingview_price(ticker):
    '''
    Takes ticker, scrapes tradingview and returns price and price change in percent.
    '''
    #initiate some values
    result = 'none'  
    resultchange = '-' 
    try:     
        tm = 0
        browser = await launch(executablePath=chrome_exec_dir, headless=True, args= chrome_exec_args)
        page = await browser.newPage()   
        charturl = tvbase + ticker
        #get up to date selectors
        css_vol = tv_css_vol
        css_close = tv_css_closeprice
        #networkidle works up to a point but need to wait for objects to actually show up for complete page load
        await page.goto(charturl, {"waitUntil" : ["load","domcontentloaded","networkidle2"]})
        ## workaround to stupid tv leftcorner/date bug on 17/3/2021
        ## await page.mouse.click(674, 1)
        print("idle chrome - waiting selector objects")              
        load = 1      
        while load == 1:
            await page.waitForSelector(css_vol, {"timeout" : 5000})
            element3 = await page.querySelector(css_vol)
            title3 = await page.evaluate('(element3) => element3.textContent', element3)  
            print(title3)
            titlelen2 = 3
            titlelen3 = len(title3) 
            tm += 1
            print(tm)
            if titlelen2 > 2 and title3 != 'n/a':
                load = 2
                break
            if titlelen2 > 2 and tm > 360:
                load = 2
                break        
        try:
            await page.waitForSelector(css_close, {"timeout" : 1000})
            elementclose = await page.querySelector(css_close)
            titleclose = await page.evaluate('(elementclose) => elementclose.textContent', elementclose)
            print(titleclose)
            result = titleclose
        except Exception as e:
            print(e)
            print('OHLC cant be found')   
            await browser.close()         
        await asyncio.sleep(0.3)

        if load == 2:
            await browser.close()
        else:
            await browser.close()
            ticker = ticker + 'btc'
            print('cant find ticker - error')
            
    except Exception as e: 
        print(e)
        await browser.close()
    return str(result), str(resultchange) 

#create db connection
def create_connection(db_file):
    ''' create a database connection to the SQLite database
        specified by db_file
    :param db_file: database file
    :return: Connection object or None
    '''
    conn = None
    try:
        conn = sqlite3.connect(db_file)
    except Exception as e:
        print(e)

    return conn

#use coingecko api for price first
def get_shitcoin(ticker):
    '''
    Takes ticker, returns price.
    '''
    x = 0
    tickerid = ''
    while x < len(dump1):
        if ticker.lower() == str(dump1[x]['symbol'].lower()):
            tickerid = str(dump1[x]['id'])
            print(tickerid)
            print('checking for valid id through mcap')
            try:
                shitcoindata = cg.get_coin_by_id(tickerid)
                shitcoinmarketcap = str(shitcoindata['market_data']['market_cap']['usd'])
                if int(shitcoinmarketcap) > 0:
                    print('found valid shitcoin')
                    break
            except Exception as e:
                print('continue search')
        x += 1

    try:
        shitcoindata = cg.get_coin_by_id(tickerid)
        #we are interested in USD prices
        shitcoinmarketcap = str(shitcoindata['market_data']['market_cap']['usd'])
        shitcoin_price = cg.get_price(ids=tickerid, vs_currencies='usd')[tickerid]['usd']
        if 'e' in str(shitcoin_price):
            shitcoin_price = str("%.17f" % shitcoin_price).rstrip('0').rstrip('.')
    except Exception as e:
        print(e)

    return str(shitcoin_price)


#crypto compare api
def get_shitcoin2(ticker):
    '''
    Takes ticker, returns price
    '''
    url1 = 'https://min-api.cryptocompare.com/data/pricemultifull?fsyms='
    url2 = '&tsyms=BTC,USD&api_key=' + str(crypto_compare_token)
    url = url1 + ticker + url2
    response = requests.get(url)
    json_data2 = json.loads(response.text)
    shitcoin_price = json_data2['DISPLAY'][ticker]['USD']['PRICE']
    return str(shitcoin_price)

#vantage not used anymore
#vantage api keys
vantage_api_step = 0
vantage_api_selection = ['xxxxxxxxxx', 'xxxxxxxxxx',
        'xxxxxxxxxx', 'xxxxxxxxxx', 'xxxxxxxxxx',
        'xxxxxxxxxx', 'xxxxxxxxxx', 'xxxxxxxxxx',
        'xxxxxxxxxx', 'xxxxxxxxxx']

def get_vantage(ticker, vantage_api_step):
    '''
    Takes ticker and api_position, returns stock price.
    '''
    #traditional markets API
    url1 = 'https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol='
    url2 = '&apikey='
    api = vantage_api_selection[vantage_api_step]
    url = url1 + ticker + url2 + api
    response = requests.get(url)
    json_data2 = json.loads(response.text)
    quote = json_data2['Global Quote']['05. price']
    return str(quote)  

###
###call, callpo, callpc, calldo, calldc, callpos ====> ticker, call_price_open, call_price_close, calldateopen, calldateclose, callposition
###

async def update_gain_losses(userid, n_instruction, channel, scorewin, scoreloss, score1):
    #updates real gain and losses score
    #on delete and close
    '''
    Takes userid, n_instruction, channel, scorewin, scoreloss, score1 and pushes changes to the database.
    '''
    conn = create_connection(database)
    serverds = time.strftime('%D')
    n_instruction = 'ratioupdate'
    if n_instruction == 'ratioupdate':
        try:
            with conn:
                cur = conn.cursor()
                print('sql geng gains losses')
                sqlc13 = '''UPDATE calls SET scorewin = ? WHERE userid = ?'''
                sqlc15 = '''UPDATE calls SET scoreloss = ? WHERE userid = ?'''
                sqlc155 = '''UPDATE calls SET score1 = ? WHERE userid = ?'''
                s13 = cur.execute(sqlc13, (scorewin, userid))   
                s15 = cur.execute(sqlc15, (scoreloss, userid))  
                s155 = cur.execute(sqlc155, (score1, userid))             
        except Exception as e: 
            print(e)
    else:
        print('i give up2')                      
        return str('error')
    return str('updated')   

async def nameupdate(userid, n_instruction, channel, usern):
    '''
    Takes userid, instruction, channel, username and updates the database.
    '''
    #updates user name
    #on every loadfield
    conn = create_connection(database)
    serverds = time.strftime('%D')
    print(usern)
    try:
        with conn:
            cur = conn.cursor()
            sqlc13 = '''UPDATE calls SET usern = ? WHERE userid = ?'''
            s13 = cur.execute(sqlc13, (usern, userid))             
    except Exception as e: 
        print(e)
    return str('updatedname')     

async def money_update(userid, n_instruction, channel, score2):
    '''
    Takes userid, n_instruction, channel, score2 and updates db.
    '''
    #updates user's money
    #on delete and close
    conn = create_connection(database)
    serverds = time.strftime('%D')
    n_instruction = 'ratioupdate'
    if n_instruction == 'ratioupdate':
        try:
            with conn:
                cur = conn.cursor()
                print('sql geng gains losses')
                sqlc13 = '''UPDATE calls SET score2 = ? WHERE userid = ?'''
                s13 = cur.execute(sqlc13, (score2, userid))           
        except Exception as e: 
            print(e)
    else:
        print('i give up2')                      
        return str('error')
    return str('updated')  

async def remember_money(userid, n_instruction, channel, money, multiplier):
    #remembers money amount when each position is opened
    '''
    Takes userid, n_instruction, channel, money, multiplier and updates db
    '''
    conn = create_connection(database)
    serverds = time.strftime('%D')
    try:
        with conn:
            cur = conn.cursor()
            print('sql geng remember money')
            if multiplier == 1:
                sqlc13 = '''UPDATE calls SET money1 = ? WHERE userid = ?'''
                s13 = cur.execute(sqlc13, (money, userid))   
            elif multiplier == 2:
                sqlc13 = '''UPDATE calls SET money2 = ? WHERE userid = ?'''
                s13 = cur.execute(sqlc13, (money, userid))  
            elif multiplier == 3:
                sqlc13 = '''UPDATE calls SET money3 = ? WHERE userid = ?'''
                s13 = cur.execute(sqlc13, (money, userid))  
            elif multiplier == 4:
                sqlc13 = '''UPDATE calls SET money4 = ? WHERE userid = ?'''
                s13 = cur.execute(sqlc13, (money, userid))  
            elif multiplier == 5:
                sqlc13 = '''UPDATE calls SET money5 = ? WHERE userid = ?'''
                s13 = cur.execute(sqlc13, (money, userid))                                                  
    except Exception as e: 
        print(e)
    return str('updated')  

async def load_data(userid, n_instruction, channel, orderby):
    '''
    Takes userid, n_instruction, channel, order and loads user data from db
    '''
    #loads data for users from db
    #also used to check for registered users and existing data
    userstatus = 0
    serverds = time.strftime('%D')
    connection = sqlite3.connect('./calls.db')
    cur = connection.cursor()
    usern2 = str((client.get_user(userid)).name)
    try:

        rows = cur.execute(
            "SELECT userid,usern,score1,score2,score3,tw,tl,scorewin,scoreloss FROM calls ORDER by ? DESC",
            (orderby,),
        ).fetchall()
        print(rows)


        try:
            userid = rows[0][0]
            usern = rows[0][1]
            score1 = rows[0][2]
            score2 = rows[0][3]
            score3 = rows[0][4]
            tw = rows[0][5]
            tl = rows[0][6]
            scorewin = rows[0][7]
            scoreloss = rows[0][8]
            if tw == None:
                tw = '0'
            if tl == None:
                tl = '0'
            if scorewin == None:
                scorewin = '0'
            if scoreloss == None:
                scoreloss = '0'      
            if score1 == None:
                score1 = '0' 
        except Exception as e:
            print(e)
                                          
    except Exception as e:
        print(e)
    return

async def update_field2delete(userid, n_instruction, channel, tw, tl):
    '''
    Takes userid, n_instruction, channel, totalwin, t1 and updates totalwin and t1 on db
    '''
    #updates specific position when called
    #usually on closing position
    conn = create_connection(database)
    serverds = time.strftime('%D')
    if n_instruction == 'ratioupdate':
        try:
            with conn:
                cur = conn.cursor()
                print('sqltw tl')
                sqlc13 = '''UPDATE calls SET tw = ? WHERE userid = ?'''
                sqlc15 = '''UPDATE calls SET tl = ? WHERE userid = ?'''
                s13 = cur.execute(sqlc13, (tw, userid))   
                s15 = cur.execute(sqlc15, (tl, userid))   
                #msg = 'updated tw tl'
                #asyncio.ensure_future(send_message(userid, channel, msg))              
        except Exception as e: 
            print(e)
    else:
        print('i give up2')                      
        return str('error')
    return str('updated')    

def create_entry(conn, entry):
    #not used anymore, replaced by initiator
    """
    Create a new entry into the entries table
    """
    sql = ''' INSERT INTO calls(userid,call1,call1po,call1pc,call1do,call1dc,call2,call2po,call2pc,call2do,call2dc,call3,call3po,call3pc,call3do,call3dc,call4,call4po,call4pc,call4do,call4dc,call5,call5po,call5pc,call5do,call5dc)
              VALUES(??????????????????????????) '''
    cur = conn.cursor()
    cur.execute(sql, entry)
    conn.commit()
    print(cur.lastrowid)
    return cur.lastrowid

async def update_tether(userid, n_instruction, channel, score2):
    '''
    Updates user's usdTether on database
    '''
    # updates total USD tether credits and last requested gibs day
    conn = create_connection(database)
    serverds = time.strftime('%D')
    lastgibs = serverds
    if n_instruction == 'gibs':
        try:
            with conn:
                cur = conn.cursor()
                print('sql gibs')
                sqlc13 = '''UPDATE calls SET score2 = ? WHERE userid = ?'''
                sqlc133 = '''UPDATE calls SET lastgibs = ? WHERE userid = ?'''
                s13 = cur.execute(sqlc13, (score2, userid))    
                s133 = cur.execute(sqlc133, (lastgibs, userid))   
                msg = 'gibsgiven'

                asyncio.ensure_future(send_message(userid, channel, msg))                
        except Exception as e: 
            print(e)
    else:
        print('i give up trying to give gibs')                      
        return str('errorgibs')
    return str('updatedgibs')    

async def update_field2(userid, callpc, calldc, n_instruction, multiplier, channel, score3, score2, tw, tl, inform):
    '''
    Updates call/position of the user in database.
    '''
    #updates specific position or multiplier when called
    #usually on closing position
    conn = create_connection(database)
    serverds = time.strftime('%D')
    if multiplier == 1 or multiplier == '1':
        try:
            with conn:
                cur = conn.cursor()
                print('sql1')
                sqlc13 = '''UPDATE calls SET call1pc = ? WHERE userid = ?'''
                sqlc15 = '''UPDATE calls SET call1dc = ? WHERE userid = ?'''
                sqlc155 = '''UPDATE calls SET score3 = ? WHERE userid = ?'''
                sqlc1555 = '''UPDATE calls SET score2 = ? WHERE userid = ?'''
                sqlc15555 = '''UPDATE calls SET tw = ? WHERE userid = ?'''
                sqlc155555 = '''UPDATE calls SET tl = ? WHERE userid = ?'''
                s13 = cur.execute(sqlc13, (callpc, userid))   
                s15 = cur.execute(sqlc15, (calldc, userid))   
                s155 = cur.execute(sqlc155, (score3, userid))  
                s1555 = cur.execute(sqlc1555, (score2, userid)) 
                s15555 = cur.execute(sqlc15555, (tw, userid))
                s155555 = cur.execute(sqlc155555, (tl, userid))
                msg = 'closed'
                asyncio.ensure_future(send_message2(userid, channel, msg, inform))              
        except Exception as e: 
            print(e)

    elif multiplier == 2 or multiplier == '2':
        try:
            with conn:
                cur = conn.cursor()
                print('sql2')
                sqlc13 = '''UPDATE calls SET call2pc = ? WHERE userid = ?'''
                sqlc15 = '''UPDATE calls SET call2dc = ? WHERE userid = ?'''
                sqlc155 = '''UPDATE calls SET score3 = ? WHERE userid = ?'''
                sqlc1555 = '''UPDATE calls SET score2 = ? WHERE userid = ?'''
                sqlc15555 = '''UPDATE calls SET tw = ? WHERE userid = ?'''
                sqlc155555 = '''UPDATE calls SET tl = ? WHERE userid = ?'''
                s13 = cur.execute(sqlc13, (callpc, userid))   
                s15 = cur.execute(sqlc15, (calldc, userid))   
                s155 = cur.execute(sqlc155, (score3, userid))  
                s1555 = cur.execute(sqlc1555, (score2, userid)) 
                s15555 = cur.execute(sqlc15555, (tw, userid))
                s155555 = cur.execute(sqlc155555, (tl, userid))
                msg = 'closed'
                asyncio.ensure_future(send_message2(userid, channel, msg, inform))                  
        except Exception as e: 
            print(e)

    elif multiplier == 3 or multiplier == '3':
        try:
            with conn:
                cur = conn.cursor()
                print('sql3')
                sqlc13 = '''UPDATE calls SET call3pc = ? WHERE userid = ?'''
                sqlc15 = '''UPDATE calls SET call3dc = ? WHERE userid = ?'''
                sqlc155 = '''UPDATE calls SET score3 = ? WHERE userid = ?'''
                sqlc1555 = '''UPDATE calls SET score2 = ? WHERE userid = ?'''
                sqlc15555 = '''UPDATE calls SET tw = ? WHERE userid = ?'''
                sqlc155555 = '''UPDATE calls SET tl = ? WHERE userid = ?'''
                s13 = cur.execute(sqlc13, (callpc, userid))   
                s15 = cur.execute(sqlc15, (calldc, userid))  
                s155 = cur.execute(sqlc155, (score3, userid))  
                s1555 = cur.execute(sqlc1555, (score2, userid)) 
                s15555 = cur.execute(sqlc15555, (tw, userid))
                s155555 = cur.execute(sqlc155555, (tl, userid)) 
                msg = 'closed'
                asyncio.ensure_future(send_message2(userid, channel, msg, inform))                   
        except Exception as e: 
            print(e)
    elif multiplier == 4 or multiplier == '4':
        try:
            with conn:
                cur = conn.cursor()
                print('sql4')
                sqlc13 = '''UPDATE calls SET call4pc = ? WHERE userid = ?'''
                sqlc15 = '''UPDATE calls SET call4dc = ? WHERE userid = ?'''
                sqlc155 = '''UPDATE calls SET score3 = ? WHERE userid = ?'''
                sqlc1555 = '''UPDATE calls SET score2 = ? WHERE userid = ?'''
                sqlc15555 = '''UPDATE calls SET tw = ? WHERE userid = ?'''
                sqlc155555 = '''UPDATE calls SET tl = ? WHERE userid = ?'''
                s13 = cur.execute(sqlc13, (callpc, userid))   
                s15 = cur.execute(sqlc15, (calldc, userid)) 
                s155 = cur.execute(sqlc155, (score3, userid))  
                s1555 = cur.execute(sqlc1555, (score2, userid)) 
                s15555 = cur.execute(sqlc15555, (tw, userid))
                s155555 = cur.execute(sqlc155555, (tl, userid)) 
                msg = 'closed'
                asyncio.ensure_future(send_message2(userid, channel, msg, inform))                    
        except Exception as e: 
            print(e)                 
    elif multiplier == 5 or multiplier == '5':
        try:
            with conn:
                cur = conn.cursor()
                print('sql5')
                sqlc13 = '''UPDATE calls SET call5pc = ? WHERE userid = ?'''
                sqlc15 = '''UPDATE calls SET call5dc = ? WHERE userid = ?'''
                sqlc155 = '''UPDATE calls SET score3 = ? WHERE userid = ?'''
                sqlc1555 = '''UPDATE calls SET score2 = ? WHERE userid = ?'''
                sqlc15555 = '''UPDATE calls SET tw = ? WHERE userid = ?'''
                sqlc155555 = '''UPDATE calls SET tl = ? WHERE userid = ?'''
                s13 = cur.execute(sqlc13, (callpc, userid))   
                s15 = cur.execute(sqlc15, (calldc, userid))  
                s155 = cur.execute(sqlc155, (score3, userid))   
                s1555 = cur.execute(sqlc1555, (score2, userid))  
                s15555 = cur.execute(sqlc15555, (tw, userid))
                s155555 = cur.execute(sqlc155555, (tl, userid))
                msg = 'closed'
                asyncio.ensure_future(send_message2(userid, channel, msg, inform))                
        except Exception as e: 
            print(e)
    else:
        print('i give up')                      
        return str('error')
    if n_instruction == 'delete':
        return str('deleted')
    return str('updated')    

#new user initiator
def create_entryinitiate(conn, entry, userid, n_instruction):
    '''
    Creates a new entry for the user, in the database.
    '''
    #initiates/registers user that cant be found in db
    try:
        sql = ''' INSERT INTO calls(userid,call1,call1po,call1pc,call1do,call1dc,call2,call2po,call2pc,call2do,call2dc,call3,call3po,call3pc,call3do,call3dc,call4,call4po,call4pc,call4do,call4dc,call5,call5po,call5pc,call5do,call5dc,call1pos,call2pos,call3pos,call4pos,call5pos,score2)
                  VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) '''
        cur = conn.cursor()
        cur.execute(sql, entry)
        conn.commit()
        print(cur.lastrowid)
    except Exception as e: 
        print(e)
    return cur.lastrowid    

#some channel cleanup for bot messages
async def notification_handler(userid, channel, msgtype, msgname, msgvalue):
    '''
    Handles notifications
    '''
    serverds = time.strftime('%D')
    embed=discord.Embed(title=msgtype, url='')
    embed.set_author(name=" ", url="", icon_url="")
    embed.add_field(name=msgname, value=msgvalue, inline=False)
    msg6 = await channel.send(embed=embed)
    await asyncio.sleep(23)
    await msg6.delete() 
    return

async def send_message2(userid, channel, msg, inform):
    '''
    Handles notifications
    '''
    #handles most messages and alerts   
    serverds = time.strftime('%D')
    if msg == 'alreadyclosed':
        embed=discord.Embed(title="Error", url='')
        embed.set_author(name=" ", url="", icon_url="")
        embed.add_field(name='Slot already closed.', value='*you can clear a slot with* **.delete slotNumber**', inline=False)
        msg6 = await channel.send(embed=embed)
        await asyncio.sleep(23)
        await msg6.delete() 
    elif msg == 'closed':
        embed=discord.Embed(title="Success", url='')
        embed.set_author(name=" ", url="", icon_url="")
        embed.add_field(name='Trade has been closed.', value=inform, inline=False)
        # embed.add_field(name='Trade has been closed.', value='*view all commands with* **.calls help**', inline=False)
        msg6 = await channel.send(embed=embed)
        await asyncio.sleep(93)
        await msg6.delete() 
    return

async def send_message(userid, channel, msg):
    '''
    Handles notifications
    '''
    #handles different set of messages and alerts  
    serverds = time.strftime('%D')
    #already closed slot msg
    if msg == 'alreadyclosed':
        embed=discord.Embed(title="Error", url='')
        embed.set_author(name=" ", url="", icon_url="")
        embed.add_field(name='Slot already closed.', value='*you can clear a slot with* **.delete slotNumber**', inline=False)
        msg6 = await channel.send(embed=embed)
        await asyncio.sleep(23)
        await msg6.delete() 
    #closed position msg
    elif msg == 'closed':
        embed=discord.Embed(title="Success", url='')
        embed.set_author(name=" ", url="", icon_url="")
        embed.add_field(name='Trade has been closed.', value='*view all commands with* **.calls help**', inline=False)
        msg6 = await channel.send(embed=embed)
        await asyncio.sleep(23)
        await msg6.delete() 
    #syntax error while indicating slot msg    
    elif msg == 'indicatorerror':
        embed=discord.Embed(title="Error", url='')
        embed.set_author(name=" ", url="", icon_url="")
        embed.add_field(name='Syntax error.', value='*you can clear a slot with* **.delete slotNumber**\nSlot numbers are 1, 2, 3, 4, 5', inline=False)
        msg6 = await channel.send(embed=embed)
        await asyncio.sleep(23)
        await msg6.delete() 
    #crypto/stock ticker error msg
    elif msg == 'noprice':
        embed=discord.Embed(title="Error", url='')
        embed.set_author(name=" ", url="", icon_url="")
        embed.add_field(name='Ticker error.', value='Ticker not found. Please try again.', inline=False)
        msg6 = await channel.send(embed=embed)
        await asyncio.sleep(23)
        await msg6.delete() 
    #userid error msg
    elif msg == 'wronguser':
        embed=discord.Embed(title="Error", url='')
        embed.set_author(name=" ", url="", icon_url="")
        embed.add_field(name='UserID error.', value='User not saved.', inline=False)
        msg6 = await channel.send(embed=embed)
        await asyncio.sleep(23)
        await msg6.delete()     
    #daily bonus given msg
    elif msg == 'gibsgiven':  
        embed=discord.Embed(title="Success", url='')
        embed.set_author(name=" ", url="", icon_url="")
        embed.add_field(name='Gibs given (250 USDT)', value='Go invest', inline=False)
        msg6 = await channel.send(embed=embed)
        await asyncio.sleep(23)
        await msg6.delete()   
    #daily bonus already claimed msg
    elif msg == 'gibs2':  
        embed=discord.Embed(title="Error", url='')
        embed.set_author(name=" ", url="", icon_url="")
        embed.add_field(name='Gibs already given today', value='Try again tomorrow', inline=False)
        msg6 = await channel.send(embed=embed)
        await asyncio.sleep(23)
        await msg6.delete()              
    return
    
###call, callpo, callpc, calldo, calldc, callpos ====> ticker, call_price_open, call_price_close, calldateopen, calldateclose, callposition
async def firsttimeuser(userid, channel, n_instruction):
    '''
    Saves new user to database.
    '''
    #initiates/registers user that cant be found in db
    #prepares data and passes it to initiator
    try:
        call1 = 'n'
        call1po = 'n'
        call1pc = 'n'
        call1do = 'n'
        call1dc = 'n'
        call2 = 'n'
        call2po = 'n'
        call2pc = 'n'
        call2do = 'n'
        call2dc = 'n'
        call3 = 'n'
        call3po = 'n'
        call3pc = 'n'
        call3do = 'n'
        call3dc = 'n'
        call4 = 'n'
        call4po = 'n'
        call4pc = 'n'
        call4do = 'n'
        call4dc = 'n'
        call5 = 'n'
        call5po = 'n'
        call5pc = 'n'
        call5do = 'n'
        call5dc = 'n'            

        call1pos = 'n'  
        call2pos = 'n'  
        call3pos = 'n'  
        call4pos = 'n'  
        call5pos = 'n'  

        score2 = '50'  

        conn = create_connection(database)
        with conn:
            print(userid)
            entry = (userid,call1,call1po,call1pc,call1do,call1dc,call2,call2po,call2pc,call2do,call2dc,call3,call3po,call3pc,call3do,call3dc,call4,call4po,call4pc,call4do,call4dc,call5,call5po,call5pc,call5do,call5dc,call1pos,call2pos,call3pos,call4pos,call5pos,score2);
            entry_id = create_entryinitiate(conn, entry, userid, n_instruction)
            print('made user')
            if n_instruction != 'call':
                await load_field(userid, n_instruction, channel)
            if n_instruction == 'call':
                return 3
            if n_instruction == 'gibs':
                score2 = '250'
                await update_tether(userid, n_instruction, channel, score2)
                return 72
    except Exception as e: 
        print(e)
        print('exception 44 first initiation')
    return

async def update_field(userid, call, callpo, callpc, calldo, calldc, callpos, n_instruction, multiplier, channel, inform):
    '''
    Updates calls/positions data in the database.
    '''
    #updates specific position when called
    #usually on opening new positions
    conn = create_connection(database)
    serverds = time.strftime('%D')
    if multiplier == 1 or multiplier == '1':
        try:
            with conn:
                cur = conn.cursor()
                print('sql1')
                sqlc11 = '''UPDATE calls SET call1 = ? WHERE userid = ?'''
                sqlc12 = '''UPDATE calls SET call1po = ? WHERE userid = ?'''
                sqlc13 = '''UPDATE calls SET call1pc = ? WHERE userid = ?'''
                sqlc14 = '''UPDATE calls SET call1do = ? WHERE userid = ?'''
                sqlc15 = '''UPDATE calls SET call1dc = ? WHERE userid = ?'''
                sqlc16 = '''UPDATE calls SET call1pos = ? WHERE userid = ?'''
                s11 = cur.execute(sqlc11, (call, userid))        
                s12 = cur.execute(sqlc12, (callpo, userid))   
                s13 = cur.execute(sqlc13, (callpc, userid))   
                s14 = cur.execute(sqlc14, (calldo, userid))   
                s15 = cur.execute(sqlc15, (calldc, userid))   
                s16 = cur.execute(sqlc16, (callpos, userid)) 
        except Exception as e: 
            print(e)

    elif multiplier == 2 or multiplier == '2':
        try:
            with conn:
                cur = conn.cursor()
                print('sql2')
                sqlc11 = '''UPDATE calls SET call2 = ? WHERE userid = ?'''
                sqlc12 = '''UPDATE calls SET call2po = ? WHERE userid = ?'''
                sqlc13 = '''UPDATE calls SET call2pc = ? WHERE userid = ?'''
                sqlc14 = '''UPDATE calls SET call2do = ? WHERE userid = ?'''
                sqlc15 = '''UPDATE calls SET call2dc = ? WHERE userid = ?'''
                sqlc16 = '''UPDATE calls SET call2pos = ? WHERE userid = ?'''
                s11 = cur.execute(sqlc11, (call, userid))        
                s12 = cur.execute(sqlc12, (callpo, userid))   
                s13 = cur.execute(sqlc13, (callpc, userid))   
                s14 = cur.execute(sqlc14, (calldo, userid))   
                s15 = cur.execute(sqlc15, (calldc, userid))   
                s16 = cur.execute(sqlc16, (callpos, userid))  
        except Exception as e: 
            print(e)

    elif multiplier == 3 or multiplier == '3':
        try:
            with conn:
                cur = conn.cursor()
                print('sql3')
                sqlc11 = '''UPDATE calls SET call3 = ? WHERE userid = ?'''
                sqlc12 = '''UPDATE calls SET call3po = ? WHERE userid = ?'''
                sqlc13 = '''UPDATE calls SET call3pc = ? WHERE userid = ?'''
                sqlc14 = '''UPDATE calls SET call3do = ? WHERE userid = ?'''
                sqlc15 = '''UPDATE calls SET call3dc = ? WHERE userid = ?'''
                sqlc16 = '''UPDATE calls SET call3pos = ? WHERE userid = ?'''
                s11 = cur.execute(sqlc11, (call, userid))        
                s12 = cur.execute(sqlc12, (callpo, userid))   
                s13 = cur.execute(sqlc13, (callpc, userid))   
                s14 = cur.execute(sqlc14, (calldo, userid))   
                s15 = cur.execute(sqlc15, (calldc, userid))   
                s16 = cur.execute(sqlc16, (callpos, userid))  
        except Exception as e: 
            print(e)
    elif multiplier == 4 or multiplier == '4':
        try:
            with conn:
                cur = conn.cursor()
                print('sql4')
                sqlc11 = '''UPDATE calls SET call4 = ? WHERE userid = ?'''
                sqlc12 = '''UPDATE calls SET call4po = ? WHERE userid = ?'''
                sqlc13 = '''UPDATE calls SET call4pc = ? WHERE userid = ?'''
                sqlc14 = '''UPDATE calls SET call4do = ? WHERE userid = ?'''
                sqlc15 = '''UPDATE calls SET call4dc = ? WHERE userid = ?'''
                sqlc16 = '''UPDATE calls SET call4pos = ? WHERE userid = ?'''
                s11 = cur.execute(sqlc11, (call, userid))        
                s12 = cur.execute(sqlc12, (callpo, userid))   
                s13 = cur.execute(sqlc13, (callpc, userid))   
                s14 = cur.execute(sqlc14, (calldo, userid))   
                s15 = cur.execute(sqlc15, (calldc, userid))   
                s16 = cur.execute(sqlc16, (callpos, userid))   
        except Exception as e: 
            print(e)                 
    elif multiplier == 5 or multiplier == '5':
        try:
            with conn:
                cur = conn.cursor()
                print('sql5')
                sqlc11 = '''UPDATE calls SET call5 = ? WHERE userid = ?'''
                sqlc12 = '''UPDATE calls SET call5po = ? WHERE userid = ?'''
                sqlc13 = '''UPDATE calls SET call5pc = ? WHERE userid = ?'''
                sqlc14 = '''UPDATE calls SET call5do = ? WHERE userid = ?'''
                sqlc15 = '''UPDATE calls SET call5dc = ? WHERE userid = ?'''
                sqlc16 = '''UPDATE calls SET call5pos = ? WHERE userid = ?'''
                s11 = cur.execute(sqlc11, (call, userid))        
                s12 = cur.execute(sqlc12, (callpo, userid))   
                s13 = cur.execute(sqlc13, (callpc, userid))   
                s14 = cur.execute(sqlc14, (calldo, userid))   
                s15 = cur.execute(sqlc15, (calldc, userid))   
                s16 = cur.execute(sqlc16, (callpos, userid))  
        except Exception as e: 
            print(e)
    else:
        return str('error')
    if n_instruction == 'delete':  
        if len(inform) < 2:
            asyncio.ensure_future(notification_handler(userid, channel, 'Success', 'Slot cleared.', '*view all commands with* **.calls help**'))
        else:
            asyncio.ensure_future(notification_handler(userid, channel, 'Done', 'Slot cleared.', inform))
        return str('deleted')
    return str('updated')

async def load_field(userid, n_instruction, channel):
    '''
    Fetches record data from the database and pushes updates.
    '''
    #loads data for users from db
    #also used to check for registered users and existing data
    userstatus = 0
    serverds = time.strftime('%D')
    connection = sqlite3.connect(database)
    cur = connection.cursor()
    #find user's name with discord id
    usern2 = str((client.get_user(userid)).name)
    try:

        rows = cur.execute(
            "SELECT userid,usern,call1,call1po,call1pc,call1do,call1dc,call2,call2po,call2pc,call2do,call2dc,call3,call3po,call3pc,call3do,call3dc,call4,call4po,call4pc,call4do,call4dc,call5,call5po,call5pc,call5do,call5dc,call1pos,call2pos,call3pos,call4pos,call5pos,score1,score2,score3,lastgibs,tw,tl,scorewin,scoreloss,money1,money2,money3,money4,money5 FROM calls WHERE userid = ?",
            (userid,),
        ).fetchall()
        print(rows)
        print(rows[0][0])
        try:
            await nameupdate(userid, n_instruction, channel, usern2)
        except:
            print('user not found ignore')
        if rows[0][0] == userid:
            #print('userid found')
            userstatus = 1
            usern = rows[0][1]
            call1 = rows[0][2]
            call1po = rows[0][3]
            call1pc = rows[0][4]
            call1do = rows[0][5]
            call1dc = rows[0][6]

            call2 = rows[0][7]
            call2po = rows[0][8]
            call2pc = rows[0][9]
            call2do = rows[0][10]
            call2dc = rows[0][11]

            call3 = rows[0][12]
            call3po = rows[0][13]
            call3pc = rows[0][14]
            call3do = rows[0][15]
            call3dc = rows[0][16]

            call4 = rows[0][17]
            call4po = rows[0][18]
            call4pc = rows[0][19]
            call4do = rows[0][20]
            call4dc = rows[0][21]

            call5 = rows[0][22]
            call5po = rows[0][23]
            call5pc = rows[0][24]
            call5do = rows[0][25]
            call5dc = rows[0][26]

            call1pos = rows[0][27]
            call2pos = rows[0][28]
            call3pos = rows[0][29]
            call4pos = rows[0][30]
            call5pos = rows[0][31]

            score1 = rows[0][32]
            score2 = rows[0][33]
            score3 = rows[0][34]

            lastgibs = rows[0][35]
            tw = rows[0][36]
            tl = rows[0][37]
            scorewin = rows[0][38]
            scoreloss = rows[0][39]

            money1 = rows[0][40]
            money2 = rows[0][41]
            money3 = rows[0][42]
            money4 = rows[0][43]
            money5 = rows[0][44]

            if tw == None:
                tw = '0'
            if tl == None:
                tl = '0'
            if scorewin == None:
                scorewin = '0'
            if scoreloss == None:
                scoreloss = '0'      
            if score1 == None:
                score1 = '0'                                           

            if n_instruction == 'get':
                if userstatus == 1:
                    return call1, call1po, call1pc, call1do, call1dc, call1pos, call2, call2po, call2pc, call2do, call2dc, call2pos, call3, call3po, call3pc, call3do, call3dc, call3pos, call4, call4po, call4pc, call4do, call4dc, call4pos, call5, call5po, call5pc, call5do, call5dc, call5pos
            if n_instruction == 'all2':
                if userstatus == 1:
                    print('found external user')
            if n_instruction == 'gibs':
                return score2, lastgibs
            if n_instruction == 'close1f':
                if userstatus == 1:
                    return call1, call1po, call1pc, call1do, call1dc, call1pos, score3, score2, tw, tl, scorewin, scoreloss, score1, money1
            if n_instruction == 'close2f':
                if userstatus == 1:
                    return call2, call2po, call2pc, call2do, call2dc, call2pos, score3, score2, tw, tl, scorewin, scoreloss, score1, money2
            if n_instruction == 'close3f':
                if userstatus == 1:
                    return call3, call3po, call3pc, call3do, call3dc, call3pos, score3, score2, tw, tl, scorewin, scoreloss, score1, money3
            if n_instruction == 'close4f':
                if userstatus == 1:
                    return call4, call4po, call4pc, call4do, call4dc, call4pos, score3, score2, tw, tl, scorewin, scoreloss, score1, money4
            if n_instruction == 'close5f':
                if userstatus == 1:
                    return call5, call5po, call5pc, call5do, call5dc, call5pos, score3, score2, tw, tl, scorewin, scoreloss, score1, money5                                                                        
    except Exception as e: 
        print(e)
        #print('user id not found, initiating')
        if n_instruction == 'all2':
            print('wronguser')
            msg = 'wronguser'
            asyncio.ensure_future(send_message(userid, channel, msg))
            return str('wronguser')

    if userstatus == 1:
        #print('success')

        if call1po != 'n':
            n1 = 1
            onestring = str(call1) + ' ' + str(call1pos) + '\n' + 'Entry: ' + str(call1po) + ' Date: ' + str(call1do) + '\n' + 'Exit: ' + str(call1pc) + ' Date: ' + str(call1dc)
            if call1pc != 'n':
                onestring = str(call1) + ' ' + str(call1pos) + '\n' + 'Entry: ' + str(call1po) + ' Date: ' + str(call1do) + '\n' + 'Exit: ' + str(call1pc) + ' Date: ' + str(call1dc)
                if n_instruction == 'close1':
                    msg = 'alreadyclosed'
                    asyncio.ensure_future(send_message(userid, channel, msg))
                    print('already closed, returning 8')
                    return userstatus, str(8)
            else:
                onestring = str(call1) + ' ' + str(call1pos) + '\n' + 'Entry: ' + str(call1po) + ' Date: ' + str(call1do) + '\n' + '*close trade with* **.close 1**' 
                if n_instruction == 'close1':
                    print('closing 1')
                    return userstatus, str(5)
        else: 
            onestring = 'empty'
            n1 = 0
        if call2po != 'n':
            n2 = 1
            twostring = str(call2) + ' ' + str(call2pos) + '\n' + 'Entry: ' + str(call2po) + ' Date: ' + str(call2do) + '\n' + 'Exit: ' + str(call2pc) + ' Date: ' + str(call2dc)
            if call2pc != 'n':
                twostring = str(call2) + ' ' + str(call2pos) + '\n' + 'Entry: ' + str(call2po) + ' Date: ' + str(call2do) + '\n' + 'Exit: ' + str(call2pc) + ' Date: ' + str(call2dc)
                if n_instruction == 'close2':
                    msg = 'alreadyclosed'
                    asyncio.ensure_future(send_message(userid, channel, msg))
                    print('already closed, returning 8')
                    return userstatus, str(8)            
            else:
                twostring = str(call2) + ' ' + str(call2pos) + '\n' + 'Entry: ' + str(call2po) + ' Date: ' + str(call2do) + '\n' + '*close trade with* **.close 2**' 
                if n_instruction == 'close2':
                    print('closing 2')
                    return userstatus, str(5)        
        else: 
            n2 = 0
            twostring = 'empty'            
        if call3po != 'n':
            n3 = 1
            threestring = str(call3) + ' ' + str(call3pos) + '\n' + 'Entry: ' + str(call3po) + ' Date: ' + str(call3do) + '\n' + 'Exit: ' + str(call3pc) + ' Date: ' + str(call3dc)
            if call3pc != 'n':
                threestring = str(call3) + ' ' + str(call3pos) + '\n' + 'Entry: ' + str(call3po) + ' Date: ' + str(call3do) + '\n' + 'Exit: ' + str(call3pc) + ' Date: ' + str(call3dc)
                if n_instruction == 'close3':
                    msg = 'alreadyclosed'
                    asyncio.ensure_future(send_message(userid, channel, msg))
                    print('already closed, returning 8')
                    return userstatus, str(8)            
            else:
                threestring = str(call3) + ' ' + str(call3pos) + '\n' + 'Entry: ' + str(call3po) + ' Date: ' + str(call3do) + '\n' + '*close trade with* **.close 3**' 
                if n_instruction == 'close3':
                    print('closing 3')
                    return userstatus, str(5)        
        else: 
            n3 = 0
            threestring = 'empty'
        if call4po != 'n':
            n4 = 1
            fourstring = str(call4) + ' ' + str(call4pos) + '\n' + 'Entry: ' + str(call4po) + ' Date: ' + str(call4do) + '\n' + 'Exit: ' + str(call4pc) + ' Date: ' + str(call4dc)
            if call4pc != 'n':
                fourstring = str(call4) + ' ' + str(call4pos) + '\n' + 'Entry: ' + str(call4po) + ' Date: ' + str(call4do) + '\n' + 'Exit: ' + str(call4pc) + ' Date: ' + str(call4dc)
                if n_instruction == 'close4':
                    msg = 'alreadyclosed'
                    asyncio.ensure_future(send_message(userid, channel, msg))
                    print('already closed, returning 8')
                    return userstatus, str(8)            
            else:
                fourstring = str(call4) + ' ' + str(call4pos) + '\n' + 'Entry: ' + str(call4po) + ' Date: ' + str(call4do) + '\n' + '*close trade with* **.close 4**' 
                if n_instruction == 'close4':
                    print('closing 4')
                    return userstatus, str(5)        
        else: 
            n4 = 0
            fourstring = 'empty'        
        if call5po != 'n':
            n5 = 1
            fivestring = str(call5) + ' ' + str(call5pos) + '\n' + 'Entry: ' + str(call5po) + ' Date: ' + str(call5do) + '\n' + 'Exit: ' + str(call5pc) + ' Date: ' + str(call5dc)
            if call5pc != 'n':
                fivestring = str(call5) + ' ' + str(call5pos) + '\n' + 'Entry: ' + str(call5po) + ' Date: ' + str(call5do) + '\n' + 'Exit: ' + str(call5pc) + ' Date: ' + str(call5dc)
                if n_instruction == 'close5':
                    msg = 'alreadyclosed'
                    asyncio.ensure_future(send_message(userid, channel, msg))
                    print('already closed, returning 8')
                    return userstatus, str(8)            
            else:
                fivestring = str(call5) + ' ' + str(call5pos) + '\n' + 'Entry: ' + str(call5po) + ' Date: ' + str(call5do) + '\n' + '*close trade with* **.close 5**' 
                if n_instruction == 'close5':
                    print('closing 5')
                    return userstatus, str(5)        
        else: 
            n5 = 0
            fivestring = 'empty'
        if score1 == None:
            score1 = 0
        if score2 == None:
            score2 = 0
        if score3 == None:
            score3 = 0
        #close pos before deleting
        if n_instruction == 'all21' or n_instruction == 'all22' or n_instruction == 'all23' or n_instruction == 'all24' or n_instruction == 'all25':
            print('all2x rule hit')
            if n_instruction == 'all21':
                if call1pc == 'n':
                    print('21 not closed, fixing')
                    return userstatus, '3'
                else:
                    print('21 closed')
                    return userstatus, '5'
            if n_instruction == 'all22':
                if call2pc == 'n':
                    print('22 not closed, fixing')
                    return userstatus, '3'
                else:
                    print('22 closed')
                    return userstatus, '5'
            if n_instruction == 'all23':
                if call3pc == 'n':
                    print('23 not closed, fixing')
                    return userstatus, '3'
                else:
                    print('23 closed')
                    return userstatus, '5'
            if n_instruction == 'all24':
                if call4pc == 'n':
                    print('24 not closed, fixing')
                    return userstatus, '3'
                else:
                    print('24 closed')
                    return userstatus, '5'
            if n_instruction == 'all25':
                if call5pc == 'n':
                    print('25 not closed, fixing')
                    return userstatus, '3'
                else:
                    print('25 closed')
                    return userstatus, '5'
        #find wl ratios
        wlratio = ratioFunction(float(tw), float(tl))
        score3 = '{0:.2f}'.format(float(score3))
        score2 = '{0:.2f}'.format(float(score2))
        footertxt = ' \n\nscore W: 0     score M: 0     total: 0     '  
        #footertxt = ' \n\nscore W: ' + str(score1) + ' score M: ' + str(score2) + ' total: ' + str(score3) 
        footertxt = ' \n\nscore: ' + str(score3) + '   W/L: ' + str(wlratio) #+ '**'
        sixstring = ' \n*open a new trade with* **.open <TICKER> LONG/SHORT**'
        if int(tw) == 0:
            tw = 0.07
        
        wlratio2 = '-'
        ##calculate average percentages for win or loss
        avggainpct = int(float(scorewin))
        avglosspct = int(float(scoreloss))
        #sixstring = 'W/L: **' + str(wlratio) + '**   user: ' + '<@!' + str(userid) + '>'
        #usern = (client.get_user(userid)).name
        #username = user.name
        #sixstring = 'avgGain: **' + str(wlratio) +'** avgLoss: **' + str(wlratio) + '**   user: **' + str((client.get_user(userid)).name) + '**'
        sixstring = 'avgGain: **' + str(avggainpct) +'%** avgLoss: **' + str(avglosspct) + '%**   USDT: $**' + str(score2) + '**'
        try:
            titlestr = 'Calls   ( ' + str((client.get_user(userid)).name) + ' )'
        except:
            titlestr = 'Calls   ( ' + str(usern) + ' )'
        embed=discord.Embed(title=titlestr, url='')
        embed.set_author(name=" ", url="", icon_url="")
        embed.add_field(name='#1', value=onestring, inline=False)
        embed.add_field(name='#2', value=twostring, inline=False)
        embed.add_field(name='#3', value=threestring, inline=False)
        embed.add_field(name='#4', value=fourstring, inline=False)
        embed.add_field(name='#5', value=fivestring, inline=False)
        embed.add_field(name='\u200b', value=sixstring, inline=False)
        try:
            print('trying to find user avatar')
            userav = client.get_user(int(userid))
            userav = str(userav.avatar_url)
            embed.set_thumbnail(url=userav)
        except Exception as e: 
            print(e)
            print('error finding avatar')
        embed.set_footer(text=footertxt) 
        print('sending')

        if n_instruction == 'all' or n_instruction == 'all2':
            await channel.send(embed=embed)

        if n_instruction == 'scan':
            return userstatus, n1, n2, n3, n4, n5, score1, score2, score3
           
    return userstatus



@client.event
async def on_ready():
    print('Logged in as', client.user.name)
    print('-ready-')
      
# async def background_loop():
#     await client.wait_until_ready()
#     while not client.is_closed:
#         await asyncio.sleep(30)
#     return

@client.event  
async def on_message(message): 
    '''
    Checks messages for commands
    '''
    rmsg = message.content
    global vantage_api_step
    rmsg2 = rmsg.upper()
    channel = message.channel
    authorid = message.author.id
    authormention = '<@!' + str(authorid) + '>'
    userid = authorid
    
    if message.author == client.user:
        return
#help menu
    elif rmsg2 == '.CALL HELP' or rmsg2 == '.CALLS HELP' or rmsg2 == '.CALLSHELP' or rmsg2 == '.CALLHELP':
        embed=discord.Embed(title="Paper Trading Help")
        embed.add_field(name='Paper Trading game (beta)', value='commands: \n**.gibs** Daily USDT bonus.\n**.calls** View your positions and stats.\n**.open <TICKER> LONG/SHORT** open a trade\n**.close <slotNumber>** closes the trade and realizes profits.\n**.delete <slotNumber>** closes trade and clears slot.\n**.calls <USER>** View stats of another user\n**.score** or **.global** To view local/global leaderboards.', inline=False)
        await channel.send(embed=embed)
        return
    #check user's balance
    elif rmsg2 == '.BALANCE':
        try:
            n_instruction = 'gibs'
            score2, lastgibs = await load_field(userid, n_instruction, channel)
            score2 = '${0:.2f}'.format(float(score2))
            await channel.send(str(score2))
        except Exception as e:
            print(e)
            print('error check tether, user not found probably')
        
#check for user's positions
    elif rmsg2 == '.CALLS' or rmsg2.startswith('.CALLS '):
        serverds = time.strftime('%D')
        n_instruction = 'all'
        print(rmsg2) 
        #await load_data(userid, n_instruction, channel, 'score2')

        if rmsg2.startswith('.CALLS '):
            print(len(rmsg2))
            if len(str(rmsg2)) > 7:

                n_instruction = 'all2'
                inputed = str(rmsg2[7:])
                inputed = inputed.replace('<', '').replace('@', '').replace('!', '').replace('>', '')
                try:
                    print('trying to load info for user')
                    userstatus = await load_field(int(inputed), n_instruction, channel)
                    print(userstatus)
                except Exception as e: 
                    print(e)
                    print(inputed)
                    print('error 89 invalid user')
                    return
        if n_instruction == 'all2':
            return
        n_instruction = 'all'
        try:
            userstatus = await load_field(authorid, n_instruction, channel)
        except Exception as e: 
            #firsttimeuser(userid)
            print(e)
            print('exception 432 calls')
            return
        #if non registered user uses calls command, initiate user
        if userstatus == 0:
            await firsttimeuser(userid, channel, n_instruction)
#delete position, will close it first if still opened to avoid exploiting
    elif rmsg2.startswith('.DELETE '):
        serverds = time.strftime('%D')
        inputed = rmsg2[8:]
        inform = ''
        params = inputed.split()
        allowed_indicators = ['1', '2', '3', '4', '5']
        num_params = len(params) 
        #ticker = params[0].upper()
        if num_params > 0:
            print('num')
            start_index = 0
            for i in range(start_index, len(params)):
                indicator = params[i].upper()
                ## looking for indicators and options
                if indicator in allowed_indicators:
                    n_instruction = 'all2' + str(indicator)
                    try:
                        userstatus, posstatus = await load_field(authorid, n_instruction, channel)
                        print('pos status: '+ str(posstatus))
                    except Exception as e: 
                        print(e)
                        print('exception 4')
                    if userstatus == 1:
                        if posstatus == '3':
                            print('cheated, might need to add loss')
                            #return
                            #################################
                            n_instruction = 'close' + str(indicator) + 'f'
                            call, callpo, callpc, calldo, calldc, callpos, score3, score2, tw, tl, scorewin, scoreloss, score1, moneyremember = await load_field(userid, n_instruction, channel)
                            print(call)                          
                            ticker = call
                            try:
                                price = get_shitcoin(ticker)
                                print(price)
                                preply = '1'
                                #price = price[2:]
                            except Exception as e: 
                                print(e)
                                preply = '0'
                            if preply == '0':
                                try:
                                    # vantage not used anymore
                                    # vantage_api_step += 1
                                    # price = get_vantage(ticker, vantage_api_step)
                                    # print(price)
                                    # preply = '01'
                                    price, qchange = await tradingview_price(ticker)
                                    if price != 'none':
                                        preply = '01'
                                    else:
                                        preply = '00'                                   
                                except Exception as e: 
                                    print(e)
                                    preply = '00'
                            print(price)
                            callpc = price
                            calldc = serverds
                            callpo = str(callpo).replace(',', '')
                            callpc = str(callpc).replace(',', '')
                            price = str(price).replace(',', '')
                            #price = float(price)
                            print(callpo)
                            print(callpc)
                            tradechange = get_change(float(callpo), float(price))
                            if score3 == None:
                                score3 = '0'
                            if score2 == None:
                                score2 = '0'
                            print('score change:')
                            print(callpos)
                            
                            postether = (float(score2) / 5) * (float(tradechange) / 100)                            
                            inf1 = '{0:.2f}'.format(float(tradechange))
                            inf2 = '{0:.2f}'.format(float(postether))
                            print(tradechange)
                            newscore = float(tradechange) / 10
                            print('add score REAL: ' + str(newscore))
                            if float(tradechange) == 0:
                                print('breakeven')
                                inform = 'Broke even at%' + str(inf1)  
                            else:                           
                                if callpos == 'LONG':
                                    if float(callpo) < float(price):
                                        print('in profit, adding win')
                                        if float(newscore) > 0:
                                            print('above .0 saving win')
                                            tw = int(tw) + 1
                                            scorewin = float(scorewin) + float(tradechange)
                                            score1 = float(score1) + float(tradechange)
                                            score2 = float(score2) + float(postether)
                                            inform = 'Position exit at %' + str(inf1) + ' and you earned ' + str(inf2) + ' USDT'
                                    else:
                                        print('in loss')
                                        if float(newscore) > 0:
                                            print('above .0 saving loss')
                                            tl = int(tl) + 1
                                            scoreloss = float(scoreloss) + float(tradechange)
                                            score1 = float(score1) - float(tradechange)
                                            score2 = float(score2) - float(postether)
                                            inform = 'Position exit at -%' + str(inf1) + ' and you lost ' + str(inf2) + ' USDT'
                                if callpos == 'SHORT':
                                    if float(callpo) > float(price):
                                        print('in profit, adding score')
                                        if float(newscore) > 0:
                                            print('above .0 saving win')
                                            tw = int(tw) + 1     
                                            scorewin = float(scorewin) + float(tradechange)
                                            score1 = float(score1) + float(tradechange)  
                                            score2 = float(score2) + float(postether)
                                            inform = 'Position exit at %' + str(inf1) + ' and you earned ' + str(inf2) + ' USDT'                             
                                    else:
                                        if float(newscore) > 0:
                                            print('above .0 saving loss')
                                            tl = int(tl) + 1 
                                            score1 = float(score1) - float(tradechange)    
                                            scoreloss = float(scoreloss) + float(tradechange)  
                                            score2 = float(score2) - float(postether)
                                            inform = 'Position exit at -%' + str(inf1) + ' and you lost ' + str(inf2) + ' USDT'                             
                                        print('in loss')
                            #await message.add_reaction('✅')
                            print('adding tw tl')
                            n_instruction = 'ratioupdate'
                            updatemoney = await money_update(userid, n_instruction, channel, score2)
                            updategainloss = await update_gain_losses(userid, n_instruction, channel, scorewin, scoreloss, score1)
                            updateres = await update_field2delete(userid, n_instruction, channel, tw, tl)

                        else:
                            print('didnt find cheat, proceeding with delete.')

                    print('deleting..')
                    n_instruction = 'delete'
                    call = 'n'
                    callpo = 'n'
                    callpc = 'n'
                    calldo = 'n'
                    calldc = 'n'
                    callpos = 'n'
                    
                    print(indicator)
                    await message.add_reaction('✅')
                    updateres = await update_field(userid, call, callpo, callpc, calldo, calldc, callpos, n_instruction, indicator, channel, inform)
                else:
                    msg = 'indicatorerror'
                    await message.add_reaction('⚠')
                    asyncio.ensure_future(send_message(userid, channel, msg))
                    return

        if userstatus == 0:
            await firsttimeuser(userid, channel, n_instruction)

#daily USD tether bonus
    elif rmsg2 == '.GIBS' or rmsg2 == '.GIB' or rmsg2 == '.DAILY':
        if daily_usd_claim != 1:
            return
        serverds = time.strftime('%D')
        n_instruction = 'gibs'
        
        try:
            userstatus = await load_field(authorid, n_instruction, channel)
        except Exception as e: 
            #firsttimeuser(userid)
            print(e)
            return
        if userstatus == 0:
            await firsttimeuser(userid, channel, n_instruction)
        
        else:
            #check if already claimed today
            score2, lastgibs = await load_field(userid, n_instruction, channel)   
            if score2 == None:
                score2 = '0'
            if str(lastgibs) == serverds:
                msg = 'gibs2'
                await message.add_reaction('⚠')
                asyncio.ensure_future(send_message(userid, channel, msg))
                return
            else:
                #update db with bonus credits for user
                await message.add_reaction('✅')
                score2 = float(score2) + daily_usd_amount
                await update_tether(userid, n_instruction, channel, score2)    

#closing positions/calls
    elif rmsg2.startswith('.CLOSE '):
        serverds = time.strftime('%D')
        userstatus = 0
        inputed = rmsg2[7:]
        params = inputed.split()
        allowed_indicators = ['1', '2', '3', '4', '5']
        num_params = len(params) 
        #ticker = params[0].upper()
        if num_params > 0:
            print('num')
            start_index = 0
            for i in range(start_index, len(params)):
                indicator = params[i].upper()
                ## looking for indicators
                if indicator in allowed_indicators:
                    n_instruction = 'close' + str(indicator)
                    try:
                        userstatus, userres = await load_field(authorid, n_instruction, channel)
                    except Exception as e: 
                        print(e)
                        print('exception 4')
                        await message.add_reaction('⚠')
                        asyncio.ensure_future(notification_handler(userid, channel, 'Error', 'Slot is empty.', 'Cannot close this trade.'))                         
                    if userstatus == 1:

                        if userres == '8':
                            print('already closed ignoring.')

                        if userres == '5':
                            print('closing..')
                            n_instruction = 'close' + str(indicator) + 'f'
                            call, callpo, callpc, calldo, calldc, callpos, score3, score2, tw, tl, scorewin, scoreloss, score1, moneyremember = await load_field(userid, n_instruction, channel)
                            ticker = call
                            try:
                                price = get_shitcoin(ticker)
                                print(price)
                                preply = '1'
                                #price = price[2:]
                            except Exception as e: 
                                print(e)
                                preply = '0'
                            if preply == '0':
                                try:
                                    # vantage replaced by tv
                                    # vantage_api_step += 1
                                    # price = get_vantage(ticker, vantage_api_step)
                                    # print(price)
                                    # preply = '01'
                                    price, qchange = await tradingview_price(ticker)
                                    if price != 'none':
                                        preply = '01'
                                    else:
                                        preply = '00'                                      
                                except Exception as e: 
                                    print(e)
                                    preply = '00'
                            print(price)
                            callpc = price
                            calldc = serverds
                            callpo = str(callpo).replace(',', '')
                            callpc = str(callpc).replace(',', '')
                            price = str(price).replace(',', '')
                            #price = float(price)
                            print(callpo)
                            print(callpc)
                            tradechange = get_change(float(callpo), float(price))
                            if score3 == None:
                                score3 = '0'
                            if score2 == None:
                                score2 = '0'
                            print('score change:')
                            print(callpos)
                            print(tradechange)
                            newscore = float(tradechange) / 10
                            postether = (float(score2) / 5) * (float(tradechange) / 100)
                            #finaltether = float(postether) + float(score2)
                            finalscore = float(score3) + float(newscore)
                            print('existing tether: ' + str(score2))
                            print('tether add: ' + str(postether))
                            print('existing score: ' + str(score3))
                            print('add score REAL: ' + str(newscore))
                            print('new score if profit: ' + str(finalscore))
                            inform = '*view all commands with* **.calls help**'
                            inf1 = '{0:.2f}'.format(float(tradechange))
                            inf2 = '{0:.2f}'.format(float(postether))
                            if float(tradechange) == 0:
                                print('breakeven')
                                inform = 'Broke even at%' + str(inf1)  
                            else:   
                                if callpos == 'LONG':
                                    if float(callpo) < float(price):
                                        print('in profit, adding score')
                                        score3 = finalscore
                                        inform = 'Position exit at %' + str(inf1) + ' and you earned ' + str(inf2) + ' USDT'
                                        if float(newscore) > 0:
                                            score2 = float(score2) + float(postether)                                        
                                            print('above .0 saving win')
                                            tw = int(tw) + 1
                                            scorewin = float(scorewin) + float(tradechange)
                                            score1 = float(score1) + float(tradechange)
                                            finaltether = float(postether) + float(score2)
                                    else:
                                        print('in loss')
                                        if float(newscore) > 0:
                                            print('above .0 saving loss')
                                            tl = int(tl) + 1
                                            scoreloss = float(scoreloss) + float(tradechange)
                                            score1 = float(score1) - float(tradechange)
                                            finaltether = float(score2) - float(postether)
                                            score2 = float(score2) - float(postether)
                                            inform = 'Position exit at -%' + str(inf1) + ' and you lost ' + str(inf2) + ' USDT'
                                if callpos == 'SHORT':
                                    if float(callpo) > float(price):
                                        print('in profit, adding score')
                                        #score2 = finaltether
                                        score3 = finalscore
                                        inform = 'Position exit at %' + str(inf1) + ' and you earned ' + str(inf2) + ' USDT' 
                                        if float(newscore) > 0:
                                            score2 = float(score2) + float(postether)                                        
                                            print('above .0 saving win')
                                            tw = int(tw) + 1
                                            scorewin = float(scorewin) + float(tradechange)
                                            score1 = float(score1) + float(tradechange)
                                            finaltether = float(postether) + float(score2)                    
                                    else:
                                        if float(newscore) > 0:
                                            score2 = float(score2) - float(postether)
                                            print('above .0 saving loss')
                                            tl = int(tl) + 1   
                                            scoreloss = float(scoreloss) + float(tradechange)
                                            score1 = float(score1) - float(tradechange)
                                            finaltether = float(score2) - float(postether)
                                            inform = 'Position exit at -%' + str(inf1) + ' and you lost ' + str(inf2) + ' USDT'                                 
                                        print('in loss')
                                   
                            await message.add_reaction('✅')
                            #score2 = finaltether
                            updategainloss = await update_gain_losses(userid, n_instruction, channel, scorewin, scoreloss, score1)
                            updateres = await update_field2(userid, callpc, calldc, n_instruction, indicator, channel, score3, score2, tw, tl, inform)
 
    #open position/call
    elif rmsg2.startswith('.CALL ') or rmsg2.startswith('.OPEN '):
        serverds = time.strftime('%D')
        if rmsg2.startswith('.CALL DELET'):
            print('ignore.')
            return
        if vantage_api_step > 9:
            vantage_api_step = 0
        print('dd')
        allowed_indicators = ['SHORT', 'LONG']
        inputed = message.content[6:]
        params = inputed.split()
        num_params = len(params) 
        ticker = params[0].upper()
        if len(ticker) > 4:
            #### genghis anti cheat
            print(str(ticker) + 'length is: ' + str(len(ticker)) + ' - trying to remove USD')
            #ticker = ticker.replace('USDT', '').replace('USD', '')
        if num_params > 0:
            if num_params == 1:
                print('invalid call options')
                return
            start_index = 1
            for i in range(start_index, len(params)):
                indicator = params[i].upper()
                ## looking for indicators and options
       
                if indicator in allowed_indicators:
                    if indicator == 'SHORT':
                        callpos = indicator
                    if indicator == 'LONG':
                        callpos = indicator
                if indicator not in allowed_indicators:
                    #print('invalid indicator')
                    await message.add_reaction('⚠')
                    asyncio.ensure_future(notification_handler(userid, channel, 'Error', 'Invalid position', '*open a new trade with* **.open TICKER LONG/SHORT**'))                 
                    return
        try:
            n_instruction = 'call'
            userstatus = await load_field(authorid, n_instruction, channel)
        except Exception as e: 
            print(e)
        if userstatus == 0:
            n_instruction = 'call'
            #print('didnt find user, creating and checking again before call')
            userstatus = await firsttimeuser(userid, channel, n_instruction)
        if userstatus == 3 or userstatus == 1:
            n_instruction = 'scan'
            userstatus, n1, n2, n3, n4, n5, score1, score2, score3 = await load_field(userid, n_instruction, channel)
            #print(str(n1) + str(n2) + str(n3) + str(n4) + str(n5))
            #print('ticker:' + ticker)
            #print('position:' + callpos)

            try:
                price = get_shitcoin(ticker)
                print(price)
                preply = '1'
                #price = price[2:]
            except Exception as e: 
                print(e)
                preply = '0'
            if preply == '0':
                try:
                    ## vantage not used anymore
                    # vantage_api_step += 1
                    # price = get_vantage(ticker, vantage_api_step)
                    # price = float(price)
                    # print(price)
                    # preply = '01'
                    price, qchange = await tradingview_price(ticker)
                    if price != 'none':
                        preply = '01'
                    else:
                        preply = '00'                      
                except Exception as e: 
                    print(e)
                    preply = '00'

            price = str(price).replace(',', '')
            price = float(price)
            n_instruction = 'update'
            try:
                inform = ''
                if preply == '00':
                    print('no price')
                #check for empty slots
                elif n1 == 0:
                    print('n1')
                    updateres = await update_field(userid, ticker, price, 'n', serverds, 'n', callpos, n_instruction, 1, channel, inform)
                    remembermoney = await remember_money(userid, n_instruction, channel, score2, 1)
                elif n2 == 0:
                    updateres = await update_field(userid, ticker, price, 'n', serverds, 'n', callpos, n_instruction, 2, channel, inform)
                    print('n2')
                    remembermoney = await remember_money(userid, n_instruction, channel, score2, 2)
                elif n3 == 0:
                    updateres = await update_field(userid, ticker, price, 'n', serverds, 'n', callpos, n_instruction, 3, channel, inform)
                    print('n3')
                    remembermoney = await remember_money(userid, n_instruction, channel, score2, 3)
                elif n4 == 0:
                    updateres = await update_field(userid, ticker, price, 'n', serverds, 'n', callpos, n_instruction, 4, channel, inform)
                    print('n4')
                    remembermoney = await remember_money(userid, n_instruction, channel, score2, 4)
                elif n5 == 0:
                    updateres = await update_field(userid, ticker, price, 'n', serverds, 'n', callpos, n_instruction, 5, channel, inform)
                    print('n5')   
                    remembermoney = await remember_money(userid, n_instruction, channel, score2, 5)
                else:
                    #no free slots available, alert user
                    #print('no empty slots')
                    updateres = 'full'
            except Exception as e: 
                print(e)
                #print('exception slotcheck')
            finally:
                #alert user if we cant find the ticker
                if preply == '00':
                    msg = 'noprice'
                    await message.add_reaction('⚠')
                    asyncio.ensure_future(send_message(userid, channel, msg))
                    return
                print(updateres)

            #print('vantage api: ' + str(vantage_api_step)) 

            if preply == '00':
                print('cant find ticker')
                await message.add_reaction('⚠')
                await channel.send('Cant find ticker.')
            else:
                if updateres == 'full':
                    await message.add_reaction('⚠')
                    await channel.send('No empty slots. You can clear a slot with **.delete slotNumber**')
                if updateres == 'error':
                    await message.add_reaction('⚠')
                    await channel.send('error')
                if updateres == 'updated':
                    updatemsg = '**' + ticker + '**' + ' trade has been saved.'
                    await message.add_reaction('✅')
                    asyncio.ensure_future(notification_handler(userid, channel, 'Success', 'Opened trade.', updatemsg))      

    elif rmsg2 == '.CALLS debugINIT5315413431431':
        n_instruction = 'all'
        try:
            print('test')
            #firsttimeuser(userid)
        except Exception as e: 
            print(e)
        return
def Main():
#    client.loop.create_task(background_loop())
    client.run(discord_token)
if __name__ == "__main__":

    Main()
