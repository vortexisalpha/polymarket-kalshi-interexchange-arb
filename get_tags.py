import requests



# POLY = "https://gamma-api.polymarket.com/"
# response = requests.get(f"{POLY}/tags").json()
#
# print(response)
# with open ('poly_tags.json', 'w') as f:
#     for tag in response:
#         f.writelines(f"{tag['label']}\n")
#

import requests
import json
BASE = "https://api.elections.kalshi.com/trade-api/v2"

tags_by_categories = requests.get(f"{BASE}/search/tags_by_categories").json()["tags_by_categories"]
print(tags_by_categories)

with open("kalshi_categories_to_tags.json", "w") as f:
    json.dump(tags_by_categories, f)

print("categories:", len(categories))
print("tags:", len(all_tags))

