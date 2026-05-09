# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "requests>=2.33.1",
# ]
# ///
import csv
import json
import logging
import requests
from io import StringIO


ITEMS_EN_URL = "https://raw.githubusercontent.com/xivapi/ffxiv-datamining/refs/heads/master/csv/en/Item.csv"
TOMESTONES_URL = "https://raw.githubusercontent.com/xivapi/ffxiv-datamining/refs/heads/master/csv/en/TomestonesItem.csv"
SPECIAL_SHOP_URL = "https://raw.githubusercontent.com/xivapi/ffxiv-datamining/refs/heads/master/csv/en/SpecialShop.csv"

logger = logging.getLogger(__name__)


# todo: investigate item_id 50977


def main():
    logging.basicConfig(level=logging.INFO, filename="log.log", filemode="w")

    items_csv = requests.get(ITEMS_EN_URL).text
    items_reader = csv.DictReader(StringIO(items_csv))
    items = [row for row in items_reader]

    tomestones = get_tomestones_mapping(items)

    special_shop_csv = requests.get(SPECIAL_SHOP_URL).text
    special_shop_reader = csv.DictReader(StringIO(special_shop_csv))

    tomestones_offers = []

    for special_shop in special_shop_reader:
        for offer_idx in range(60):
            received_items = {}
            for item_idx in range(2):
                item_key = f"Item[{offer_idx}].Item[{item_idx}]"
                item_id = int(special_shop[item_key])

                if item_id == 0:
                    continue

                item = items[item_id]
                if item["IsUntradable"] == "True":
                    # logger.info(f"Untradable item: {item["Name"]}")
                    continue

                receive_count_key = f"Item[{offer_idx}].ReceiveCount[{item_idx}]"
                receive_count = int(special_shop[receive_count_key])

                if receive_count <= 0:
                    # logger.warning(f"Offer {offer_idx} item {item_idx} receive_count {receive_count}")
                    continue

                if item_id in received_items:
                    logger.error(f"Item {item_id} was already present in this offer")

                received_items[item_id] = receive_count

            if len(received_items) == 0:
                continue

            item_names = [
                f'"{items[item_id]["Name"]}"x{item_count}'
                for (item_id, item_count) in received_items.items()
            ]
            logger.info(f"""Offer {offer_idx} items: {item_names}""")

            has_tomes_cost = False
            has_other_cost = False
            tomes_cost = {}
            for currency_idx in range(3):
                cost_type_key = f"Item[{offer_idx}].CostType[{currency_idx}]"
                currency_id_key = f"Item[{offer_idx}].ItemCost[{currency_idx}]"  # note: naming is on purpose, this is "which item will be spent to buy"
                currency_amount_key = f"Item[{offer_idx}].CurrencyCost[{currency_idx}]"

                cost_type = special_shop[cost_type_key]
                currency_id = int(special_shop[currency_id_key])
                currency_amount = int(special_shop[currency_amount_key])

                logger.info(
                    f"Cost {currency_idx}: {cost_type} {currency_id} {currency_amount}"
                )

                is_tomes_currency = cost_type == "2"
                is_nothing = (
                    cost_type == "0" and currency_id == 0 and currency_amount == 0
                )

                if is_tomes_currency and currency_id not in tomestones:
                    logger.error(
                        f"Unknown tomestones {cost_type} {currency_id} {currency_amount}"
                    )

                if is_tomes_currency:
                    has_tomes_cost = True

                    if currency_id in tomes_cost:
                        logger.error(
                            f"Tomestones {currency_id} were already added as cost"
                        )

                    tomes_cost[currency_id] = currency_amount

                if (not is_tomes_currency) and (not is_nothing):
                    has_other_cost = True

            if has_tomes_cost and has_other_cost:
                # There are recipes for sword + shield + tomes, but gear is untradable, so we never reach this
                logger.error(f"Item has both tomes and other cost: {item_names}")
                continue

            if not has_tomes_cost:
                logger.info("Skip: doesn't cost tomes")
                continue

            if len(received_items) > 1:
                logger.warning("Multiple items in one offer")
                pass

            logger.info(f"Adding {received_items} {tomes_cost}")
            tomestones_offers.append((received_items, tomes_cost))

    with open("items_mapping.json", "w") as items_mapping_file:
        items_mapping = [{"en": item["Name"]} for item in items]
        json.dump(items_mapping, items_mapping_file)

    with open("tomestones_mapping.json", "w") as tomestones_mapping_file:
        json.dump(tomestones, tomestones_mapping_file)

    with open("tomestones_items.json", "w") as tomestones_items_file:
        json.dump(tomestones_offers, tomestones_items_file)


def get_tomestones_mapping(items: list[dict]) -> dict[int, dict]:
    tomestones_csv = requests.get(TOMESTONES_URL).text
    tomestones_reader = csv.DictReader(StringIO(tomestones_csv))
    tomestones = {}

    for tomestone in tomestones_reader:
        if tomestone["Tomestones"] == "0":
            # Not one of currently available tomestones
            continue

        # each tomestone has 2 ids: Item and Tomestones
        tomestone_special_id = int(tomestone["Tomestones"])
        item_id = int(tomestone["Item"])
        item = items[item_id]

        tomestones[tomestone_special_id] = {
            "name": item["Name"],
            "icon": int(item["Icon"]),
        }

    return tomestones


if __name__ == "__main__":
    main()
