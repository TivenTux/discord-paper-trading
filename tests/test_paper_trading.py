import unittest
from src import main

class TestShitcoins(unittest.TestCase):
    def test_coingecko(self):
        '''
        Test that we can get crypto ticker price.
        '''
        data = 'BTC'
        expected = 1
        result = main.get_shitcoin(data)
        print(result)
        assert float(result) > int(expected)
