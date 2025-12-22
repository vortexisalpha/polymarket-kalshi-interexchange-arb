import requests

BASE = "https://api.elections.kalshi.com/trade-api/v2"

series_params = {"limit" : 100, "category" : "Crypto"}

series_data = requests.get(f"{BASE}/series", params=series_params).json()
series_list = series_data.get("series", [])

ticker_to_title = {}

for series in series_list:
    print(f"Series Title: {series['title']}")
    ticker_to_title[series["ticker"]] = series["title"]

with open("kalshi_crypto_series.txt", "w") as f:
    for series in series_list:
       f.writelines(f"{series['title']}\n") 