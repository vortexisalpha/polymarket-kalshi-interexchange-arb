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
        if not market:
            return
        outcomes = json.loads(market.get("outcomes"))
        outcome_prices = json.loads(market.get("outcomePrices"))
        question = market.get("question")
        if 1 not in outcome_prices:
            print(f"Poly: {question}")
            for outcome, price in zip(outcomes, outcome_prices):
                print(f"{outcome}: {price}")

    #this assumes yes/no market
    def get_market_yes_no_price(self,market):
        if not market:
            return
        outcome_prices = json.loads(market.get("outcomePrices"))
        return outcome_prices[0], outcome_prices[1]



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
        if not market:
            return
        print(f"Kalshi: {market['title']} {market['yes_sub_title']}")
        print(f"yes ask: {market['yes_ask']}")
        print(f"no ask: {market['no_ask']}")
    
    def get_market_yes_no_price(self, market):
        if not market:
            return
        
        return market['yes_ask'], market['no_ask']
class ArbitragePair:
    def __init__(self, k_title, k_yes_price, k_no_price, p_title, p_yes_price, p_no_price):
        self.kalshi_title = k_title
        self.kalshi_yes_price = float(k_yes_price)/100
        self.kalshi_no_price = float(k_no_price)/100

        self.poly_title = p_title
        self.poly_yes_price = float(p_yes_price)
        self.poly_no_price = float(p_no_price)

        self.arbitrage = "none" #none for no, pk for yes poly and no kalshi, kp for yes kalshi no poly, both for both
        self.arbitrage = self.check_arb()
    def check_arb(self):
        if self.kalshi_no_price + self.poly_yes_price < 1 and self.kalshi_yes_price + self.poly_no_price < 1:
            if self.kalshi_no_price + self.poly_yes_price < self.kalshi_yes_price + self.poly_no_price:
                self.arbitrage = "pk"
            else:
                self.arbitrage = "kp"
        elif self.kalshi_no_price + self.poly_yes_price < 1:
            self.arbitrage = "pk"
        elif self.poly_no_price + self.kalshi_yes_price < 1:
            self.arbitrage = "kp"
        return self.arbitrage
    
    def print(self):
        if self.arbitrage == "none":
            return
    
        print("="*80) 
        
        print("\nKALSHI")
        print(f"  Title: {self.kalshi_title}")
        print(f"  YES:   {self.kalshi_yes_price:.4f}")
        print(f"  NO:    {self.kalshi_no_price:.4f}")

        print("\nPOLYMARKET")
        print(f"  Title: {self.poly_title}")
        print(f"  YES:   {self.poly_yes_price:.4f}")
        print(f"  NO:    {self.poly_no_price:.4f}")

        if (self.arbitrage == "kp"):
            edge = 1 - (self.poly_no_price + self.kalshi_yes_price)
            print("\nBuy yes on Kalshi, No on Polymarket\n")
        else:
            edge = 1 - (self.poly_yes_price + self.kalshi_no_price) 
            print("\nBuy yes on Polymarket, No on Kalshi\n")
        print(f"Edge = {edge}\n")
        print("="*80)


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

    #matching_pairs = get_matching_pairs(poly_titles_in = bitcoin_poly_markets,kalshi_titles_in = bitcoin_kalshi_markets)
    with open("arb_pairs.json", "r") as f:
        matching_pairs = json.load(f)

    pair_list = [] 
    #print matching arb pairs
    for matching_pair in matching_pairs:
        poly_title = matching_pair['poly_title']
        poly_market = poly_extractor.title_to_markets.get(poly_title, {})
        kalshi_title = matching_pair['kalshi_title']
        kalshi_market = kalshi_extractor.title_to_markets.get(kalshi_title, {})


        p_yes, p_no = poly_extractor.get_market_yes_no_price(poly_market)
        k_yes, k_no = kalshi_extractor.get_market_yes_no_price(kalshi_market)

        pair_list.append(ArbitragePair(kalshi_title, k_yes, k_no, poly_title, p_yes, p_no))
        #poly_extractor.print_market(poly_market)
        #print("\n")
        #kalshi_extractor.print_market(kalshi_market)
        #print("\n"*3)
    
    arbitrage_pair_list = [pair for pair in pair_list if pair.arbitrage != "none"]

    print('Arb Pairs:')
    for arb_pair in arbitrage_pair_list:
        arb_pair.print()
        