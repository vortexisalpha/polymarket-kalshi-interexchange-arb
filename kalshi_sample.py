import requests

BASE = "https://api.elections.kalshi.com/trade-api/v2"

series_params = {"limit" : 1000, "category" : "Crypto", "tags" : "BTC"}

series_data = requests.get(f"{BASE}/series", params=series_params).json()
series_list = series_data.get("series", [])

ticker_to_title = {}



all_series = []
while True:
    resp = requests.get(f"{BASE}/series", params=series_params).json()
    series = resp.get("series", [])
    all_series.extend(series)

    cursor = resp.get("cursor")
    if not cursor:
        break

    series_params["cursor"] = cursor

for series in all_series:
    print(f"Series Title: {series['title']}")
    ticker_to_title[series["ticker"]] = series["title"]

'''
with open("kalshi_crypto_series.txt", "w") as f:
    for series in series_list:
       f.writelines(f"{series['title']}\n") 
'''