# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "jinja2>=3.1.6",
#     "requests>=2.33.1",
# ]
# ///
import requests
import json
import logging
import datetime

from jinja2 import Environment, FileSystemLoader, select_autoescape

from pathlib import Path

USER_AGENT = "tomestogil/0.1.0"
headers = {"User-Agent": USER_AGENT}

UNIVERSALIS_BASE_URL = "https://universalis.app/api/v2/aggregated/"

logger = logging.getLogger(__name__)

env = Environment(
    loader=FileSystemLoader(Path(__file__).parent / "templates"),
    autoescape=select_autoescape(),
)


def main():
    with open("tomestones_items.json") as tomestones_items_file:
        tomestones_items = json.load(tomestones_items_file)

    with open("items_mapping.json") as items_mapping_file:
        items = json.load(items_mapping_file)

    with open("tomestones_mapping.json") as tomestones_mapping_file:
        tomestones_mapping = json.load(tomestones_mapping_file)

    all_item_ids = list(
        set(int(item_id) for (items, _) in tomestones_items for item_id in items)
    )

    market_data = {}
    for slice_start in range(0, len(all_item_ids), 100):
        ids_slice = all_item_ids[
            slice_start : min(len(all_item_ids), slice_start + 100)
        ]
        url = (
            UNIVERSALIS_BASE_URL
            + "Japan/"
            + ",".join(str(item_id) for item_id in ids_slice)
        )
        print(url)

        res = requests.get(url, headers=headers).json()

        if len(res["failedItems"]) > 0:
            logger.error(f"Failed to query items {res['failedItems']}")

        for item in res["results"]:
            market_data[item["itemId"]] = item

    with open("universalis.json", "w") as universalis_file:
        json.dump(market_data, universalis_file)

    with open("universalis.json", "r") as universalis_file:
        market_data = json.load(universalis_file)

    table_rows = []
    processed_offers = set()
    for received_items, price in tomestones_items:
        if len(received_items) > 1:
            logger.error(
                "Buying more that one item type with tomestones is not supported"
            )
            continue
        if len(price) > 1:
            logger.error(
                "Items that cost more than a single type of tomestones are not supported"
            )
            continue

        item_id, quantity = next(iter(received_items.items()))
        item_id = int(item_id)

        if quantity == 1:
            item_name = items[item_id]["en"]
        else:
            item_name = f"{items[item_id]['en']} x{quantity}"

        tomestone_id, tomestone_price = next(iter(price.items()))
        tomestone_name = tomestones_mapping[tomestone_id]["name"]
        tomestone_icon = get_icon_url(tomestones_mapping[tomestone_id]["icon"])

        offer_key = (item_id, quantity, tomestone_id, tomestone_price)
        if offer_key in processed_offers:
            logger.warning(f"Duplicate offer {offer_key}")
            continue
        processed_offers.add(offer_key)

        if str(item_id) not in market_data:
            logger.error(f"No market data for item {item_id} {item_name}")
            continue

        item_data = market_data[str(item_id)]
        mb_price = item_data["nq"]["averageSalePrice"].get("region", {}).get("price", 0)
        mb_price = int(round(mb_price))
        volume = (
            item_data["nq"]["dailySaleVelocity"].get("region", {}).get("quantity", 0)
        )
        volume = int(round(volume))

        profit_per_tome = mb_price * quantity / tomestone_price
        profit_per_tome = round(profit_per_tome, 2)

        table_rows.append(
            (
                item_name,
                tomestone_price,
                tomestone_name,
                mb_price,
                volume,
                profit_per_tome,
                tomestone_icon,
            )
        )

    table_rows.sort(key=lambda r: r[5], reverse=True)

    now_utc = datetime.datetime.now(datetime.UTC)
    last_updated = now_utc.strftime("%Y-%m-%d")

    template = env.get_template("index.html")
    with open("index.html", "w") as output_file:
        output_file.write(
            template.render(
                items=table_rows, last_update_time=last_updated
            )
        )

def get_icon_url(icon: int) -> str:
    base = (icon // 1000) * 1000
    return f"https://v2.xivapi.com/api/asset?format=png&path=ui/icon/{base:06d}/{icon:06d}.tex"

if __name__ == "__main__":
    main()
