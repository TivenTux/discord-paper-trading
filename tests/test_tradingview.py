import unittest
import asyncio
from src import main

class TestAsync(unittest.IsolatedAsyncioTestCase):
    async def test_tradingview(self):
        '''
        Test that we can get OHLC data from tradingview.
        '''
        data = 'TSLA'
        expected = 0
        result, resultchange = await main.tradingview_price(data)
        print(result)
        assert float(result) > expected
