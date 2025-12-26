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
    # returns yes price, no price and link to market
    def get_market_yn_link(self,market):
        if not market:
            return None, None, None
        outcome_prices = json.loads(market.get("outcomePrices"))
        if not outcome_prices or len(outcome_prices) < 2:
            return None, None, None
        slug = market['slug']
        if not slug:
            return None, None, None
        link = f"https://polymarket.com/market/{slug}"
        return outcome_prices[0], outcome_prices[1], link
        



class KalshiExtractor:
    def __init__(self):
        self.BASE = "https://api.elections.kalshi.com/trade-api/v2"
        self.title_to_ticker = {}
        self.title_to_markets = {}
        self.event_to_series = {}

    def get_series(self, category, tag):
        if tag is not None:
            series_params = {"limit" : 1000, "category" : category, "tags" : tag}
        else:
            series_params = {"limit" : 1000, "category" : category}

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

    def get_series_ticker_for_event(self, event_ticker): 
        if event_ticker in self.event_to_series:
            return self.event_to_series[event_ticker]

        r = requests.get(f"{self.BASE}/events/{event_ticker}")
        r.raise_for_status()
        series_ticker = r.json()["event"]["series_ticker"]  # docs: event has series_ticker :contentReference[oaicite:3]{index=3}
        self.event_to_series[event_ticker] = series_ticker
        return series_ticker   

    def get_market_yn_link(self, market):
        if not market:
            return None, None, None
        
        event_ticker = market['event_ticker']
        if not event_ticker:
            return None, None, None
        series_ticker = self.get_series_ticker_for_event(event_ticker)

        link = f"https://kalshi.com/markets/{series_ticker.lower()}"

        return market['yes_ask'], market['no_ask'], link

class ArbitragePair:
    def __init__(self, k_title, k_yes_price, k_no_price, k_link, p_title, p_yes_price, p_no_price, p_link):
        self.kalshi_title = k_title
        self.kalshi_yes_price = float(k_yes_price)/100
        self.kalshi_no_price = float(k_no_price)/100
        self.kalshi_link = k_link

        self.poly_title = p_title
        self.poly_yes_price = float(p_yes_price)
        self.poly_no_price = float(p_no_price)
        self.poly_link = p_link 
 
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
            self.edge = 1 - (self.poly_yes_price + self.kalshi_no_price) 
        elif self.poly_no_price + self.kalshi_yes_price < 1:
            self.arbitrage = "kp"
            self.edge = 1 - (self.poly_no_price + self.kalshi_yes_price)
        return self.arbitrage
    
    def print(self):
        if self.arbitrage == "none":
            return
    
        print("="*80) 
        
        print("\nKALSHI")
        print(f"  Title: {self.kalshi_title}")
        print(f"  YES:   {self.kalshi_yes_price:.4f}")
        print(f"  NO:    {self.kalshi_no_price:.4f}")
        print(f"  LINK:    {self.kalshi_link}")

        print("\nPOLYMARKET")
        print(f"  Title: {self.poly_title}")
        print(f"  YES:   {self.poly_yes_price:.4f}")
        print(f"  NO:    {self.poly_no_price:.4f}")
        print(f"  LINK:    {self.poly_link}")

        if (self.arbitrage == "kp"):
            print("\nBuy yes on Kalshi, No on Polymarket\n")
        else:
            print("\nBuy yes on Polymarket, No on Kalshi\n")
        print(f"Edge = {self.edge:.4%}\n")
        print("="*80)


def write_to_file(filepath, data):
    with open(filepath, "w") as f:
        for event in data:
            f.writelines(f"{event['title']}\n")



if __name__ == "__main__":
    poly_extractor = PolyExtractor()
    kalshi_extractor = KalshiExtractor()    

    bitcoin_events = poly_extractor.get_events("Trump")
    bitcoin_series = []
    bitcoin_series.extend(kalshi_extractor.get_series(category="Politics", tag="Trump Agenda"))
    bitcoin_series.extend(kalshi_extractor.get_series(category="Politics", tag="Trump Policies"))

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
    #
    # with open("arb_pairs.json", "r") as f:
    #     matching_pairs = json.load(f)
    #
    pair_list = [] 
    #print matching arb pairs
    for matching_pair in matching_pairs:
        poly_title = matching_pair['poly_title']
        poly_market = poly_extractor.title_to_markets.get(poly_title, {})
        kalshi_title = matching_pair['kalshi_title']
        kalshi_market = kalshi_extractor.title_to_markets.get(kalshi_title, {})


        p_yes, p_no, p_link = poly_extractor.get_market_yn_link(poly_market)
        k_yes, k_no, k_link = kalshi_extractor.get_market_yn_link(kalshi_market)
        
        if None in (kalshi_title, k_yes, k_no, k_link, poly_title, p_yes, p_no, p_link):    
            continue
        pair_list.append(ArbitragePair(kalshi_title, k_yes, k_no, k_link, poly_title, p_yes, p_no, p_link))

        #poly_extractor.print_market(poly_market)
        #print("\n")
        #kalshi_extractor.print_market(kalshi_market)
        #print("\n"*3)
    
    arbitrage_pair_list = [pair for pair in pair_list if pair.arbitrage != "none"]

    arbitrage_pair_list.sort(key=lambda x: x.edge)
    print('Arb Pairs:')
    for arb_pair in arbitrage_pair_list:
        arb_pair.print()
        
