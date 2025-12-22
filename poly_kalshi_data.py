import requests
import time
import json
from openai_matching_layer import get_matching_pairs
class PolyExtractor:
    def __init__(self):
        self.BASE = "https://gamma-api.polymarket.com/"
        self.title_to_ticker = {}
         
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
            self.title_to_ticker[event['title']] = event['ticker']

        return events

class KalshiExtractor:
    def __init__(self):
        self.BASE = "https://api.elections.kalshi.com/trade-api/v2"
        self.title_to_ticker = {}
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

    def get_individual_series_data(self, title):
        series_id = self.title
def write_to_file(filepath, data):
    with open(filepath, "w") as f:
        for event in data:
            f.writelines(f"{event['title']}\n")
            
if __name__ == "__main__":
    poly_extractor = PolyExtractor()

    bitcoin_events = poly_extractor.get_events("Bitcoin")
    print("Poly series data:")
    for bitcoin_event in bitcoin_events:
        print(bitcoin_event['title'])

    kalshi_extractor = KalshiExtractor()    

    bitcoin_series = kalshi_extractor.get_series(category="Crypto", tags="BTC")
    print("\n"*3 + "Kalshi series data:")
    for bitcoin_event in bitcoin_series:
        print(bitcoin_event['title'])

    '''
    write_to_file("poly_btc_events.txt", bitcoin_events)
    write_to_file("kalshi_crypto_series.txt", bitcoin_series)
    '''    

    #matching_pairs = get_matching_pairs(poly_titles_in = bitcoin_events,kalshi_titles_in = bitcoin_series)
    with open("arb_pairs.json", "r") as f:
        matching_pairs = json.load(f)

    for matching_pair in matching_pairs:
        poly_title = matching_pair['poly_title']
        kalshi_title = matching_pair['kalshi_title']

        print(f"Poly title: {poly_title}")
        print(f"Poly ID: {poly_extractor.title_to_ticker[poly_title]}")
        print(f"Kalshi title: {kalshi_title}")
        print(f"Kalshi ID: {kalshi_extractor.title_to_ticker[kalshi_title]}")

