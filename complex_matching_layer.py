from run_engine import Engine
from dataclass import dataclass


@dataclass
class Market:
    title: str
    yes_price: float
    no_price: float
    close_time: date
    market_type: str


class MatchingEngine(Engine):
    def __init__(self):
        super.__init__(self)
        self.complex_matcher = ComplexMatcher()

    def get_matching_markets(self):
        # this function takes in (from self) titles and outputs matching market titles
        # we need to change this to take in markets, give the markets to complex matching engine functions and return matching pairs

        poly_ttm = self.poly_extractor.title_to_markets
        kalshi_ttm = self.kalshi_extractor.title_to_markets

        self.matching_pairs = self.complex_matcher.get_matching_pairs(
            poly_ttm, kalshi_ttm)
        pass


class ComplexMatcher:
    def __init__(self):
        pass

    def format_ttms(self, poly_ttm, kalshi_ttm):
        # takes in title to market dictionary and returns a list of Market objects:
        #     title, yes_price, no_price, close_time
        kalshi_market_list = []

        market_type = "kalshi"
        for market in kalshi_ttm.values():
            title = market['title']
            yes_price = float(market['yes_ask'])
            no_price = float(market['no_ask'])
            close_time = datetime(market['close_time'])
            kalshi_market_list.append(
                Market(title, yes_price, no_price, close_time, market_type))

        poly_market_list = []

        market_type = "poly"
        for market in poly_ttm.values():
            title = market['title']
            yes_price = float(market['yes_ask'])
            no_price = float(market['no_ask'])
            close_time = datetime(market['close_time'])
            kalshi_market_list.append(
                Market(title, yes_price, no_price, close_time, market_type))

    def get_matching_pairs(self, poly_ttm, kalshi_ttm):
        kalshi_market_list, poly_market_list = self.format_ttms(
            poly_ttm, kalshi_ttm)
