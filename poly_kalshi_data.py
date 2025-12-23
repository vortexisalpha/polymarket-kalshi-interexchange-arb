import requests
import time
import json
from openai_matching_layer import get_matching_pairs
class PolyExtractor:
    def __init__(self):
        self.BASE = "https://gamma-api.polymarket.com/"
        self.title_to_markets = {}
         
    def get_tag_id(self, tag_name : str):
        all_tags = requests.get(f"{self.BASE}/tags").json()
        for tag in all_tags:
            if tag['label'].lower() == tag_name.lower():
                tag_id = tag['id']
                return tag_id
        print("[ERROR] did not find tag") 
        return None
    
    def get_events(self, tag_name = None, closed = "false", limit = 1000):
        event_params = {"limit" : limit,
                 "closed" : closed}
        if tag_name:
           event_params["tag_id"] = self.get_tag_id(tag_name)

        events = requests.get(f"{self.BASE}/events", params=event_params).json()
        
        for event in events:
            markets = event['markets']
            for market in markets:
                self.title_to_markets[market["question"]] = market

        return events
    
    def get_markets(self, events):
        return events['markets']

    def print_market(self, market):
        outcomes = json.loads(market.get("outcomes"))
        outcome_prices = json.loads(market.get("outcomePrices"))
        question = market.get("question")
        if 1 not in outcome_prices:
            print(f"Poly: {question}")
            for outcome, price in zip(outcomes, outcome_prices):
                print(f"{outcome}: {price}")


class KalshiExtractor:
    def __init__(self):
        self.BASE = "https://api.elections.kalshi.com/trade-api/v2"
        self.title_to_ticker = {}
        self.title_to_markets = {}
    def get_series(self, category, tags):
        series_params = {"limit" : 1000, "category" : category, "tags" : tags}

        all_series = []
        while True:
            series_data = requests.get(f"{self.BASE}/series", params=series_params).json()
            series = series_data.get("series", [])
            all_series.extend(series)

            cursor = series_data.get("cursor")
            if not cursor:
                break

            series_params["cursor"] = cursor
            time.sleep(1/19) 
        for series in all_series:
            self.title_to_ticker[series['title']] = series['ticker']

        return all_series

    def get_markets(self, ticker, limit = 100):
        market_params = {"series_ticker" : ticker, "limit" : limit, "status" : "open"}

        markets = requests.get(f"{self.BASE}/markets", params=market_params).json()['markets']

        for market in markets:
            self.title_to_markets[f"{market['title']} {market['yes_sub_title']}"] = market
        return markets

    def print_market(self, market):
        print(f"Kalshi: {market['yes_sub_title']}")
        print(f"yes ask: {market['yes_ask']}")
        print(f"no ask: {market['no_ask']}")

def write_to_file(filepath, data):
    with open(filepath, "w") as f:
        for event in data:
            f.writelines(f"{event['title']}\n")

if __name__ == "__main__":
    poly_extractor = PolyExtractor()
    kalshi_extractor = KalshiExtractor()    

    bitcoin_events = poly_extractor.get_events("Bitcoin")
    bitcoin_series = kalshi_extractor.get_series(category="Crypto", tags="BTC")

    #get list of all markets under all series/events related to category specified
    bitcoin_poly_markets = []         
    bitcoin_kalshi_markets = []         

    for event in bitcoin_events:
        markets = poly_extractor.get_markets(event)
        for market in markets:
            bitcoin_poly_markets.append(market['question'])

    for series in bitcoin_series:
        markets = kalshi_extractor.get_markets(series['ticker'])
        for market in markets:
            bitcoin_kalshi_markets.append(f"{market['title']} {market['yes_sub_title']}")

    print(f"len of poly markets {len(bitcoin_poly_markets)}")
    print(f"len of kalshi markets {len(bitcoin_kalshi_markets)}")

    matching_pairs = get_matching_pairs(poly_titles_in = bitcoin_poly_markets,kalshi_titles_in = bitcoin_kalshi_markets)
    '''
    with open("arb_pairs.json", "r") as f:
        matching_pairs = json.load(f)
    '''
    for matching_pair in matching_pairs:
        poly_title = matching_pair['poly_title']
        poly_market = poly_extractor.title_to_markets[poly_title]
        kalshi_title = matching_pair['kalshi_title']
        kalshi_market = kalshi_extractor.title_to_markets[kalshi_title]

        poly_extractor.print_market(poly_market)

        print("\n")

        print(f"Kalshi: {kalshi_title}")
        kalshi_extractor.print_market(kalshi_market)

        print("\n"*3)
