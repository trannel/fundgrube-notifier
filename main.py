import json
import logging as log
import os.path
from datetime import datetime

import pandas as pd
import requests
from bs4 import BeautifulSoup

log.basicConfig(level=log.DEBUG)

chains = [
    {
        "name": "Saturn",
        "url": "https://schneinet.de/saturn.html"
    },
    {
        "name": "MM",
        "url": "https://schneinet.de/mediamarkt.html"
    }]


def request(chain: chains) -> str:
    filename_html = f"{chain['name']}.html"

    if os.path.isfile(filename_html):
        timestamp = os.path.getmtime(filename_html)
        time_diff = datetime.now().timestamp() - timestamp
        if time_diff < 50 * 60:
            with open(filename_html, "r", encoding="utf-8") as file:
                log.debug("Loaded items from file")
                return file.read()
    html = requests.get(chain["url"]).content
    with open(filename_html, "wb") as file:
        file.write(html)
    return html.decode("utf-8")

    # print(response.status_code)
    # print(response.content)
    # TODO error handling


def create_new_items() -> pd.DataFrame:
    with open("terms.json", "r", encoding="utf-8") as search_file:
        terms = json.load(search_file)
    df = pd.DataFrame({})

    for chain in chains:
        log.info(f"Request {chain['name']} data")
        html = request(chain)
        log.info("Create soup")
        soup = BeautifulSoup(html, 'html.parser')
        log.info("Parse soup")
        body = soup.body

        for term_obj in terms:
            tags = body.find_all('a', text=lambda text: text and all(
                [term in text.lower() for term in term_obj["terms"]]))
            stores = [tag.find_parent("div").previous_sibling.contents[0].text.strip() for tag in
                      tags]
            images = [tag.get("href") for tag in tags]
            names = [tag.text for tag in tags]
            prices = [tag.parent.previous_sibling.contents[0].text for tag in tags]
            df_tmp = pd.DataFrame(
                {"name": names, "price": prices, "store": stores, "image": images})
            if df_tmp.size > 0:
                df_tmp["store"] = chain["name"] + " - " + df_tmp["store"]
            df = pd.concat([df, df_tmp])
    return df


def load_old_items(filename: str) -> pd.DataFrame:
    log.info("Load previous results")
    if os.path.isfile(filename):
        return pd.read_csv(filename, header=0, encoding="utf-8",
                           dtype={"name": "object", "price": "object", "store": "object",
                                  "image": "object"}, parse_dates=["time"])
    else:
        return pd.DataFrame({"name": [], "price": [], "store": [], "image": [], "time": []})


def process_dfs(df_new: pd.DataFrame, df_old: pd.DataFrame):
    df = pd.merge(left=df_new, right=df_old, how="left", on=["name", "price", "store", "image"])
    new_count = df["time"].isna().sum()

    df["time"] = df["time"].fillna(datetime.now())
    # TODO better notifications
    df = df.sort_values(by=["time"], ascending=False)

    log.info(f"There were {new_count} new results")
    if new_count > 0:
        pd.set_option('display.max_rows', None)
        pd.set_option('display.max_columns', None)
        pd.set_option('display.width', None)
        pd.set_option('display.max_colwidth', None)
        log.info(df[0:new_count])

    log.info("Save results")
    df.to_csv(filename, encoding="utf-8", index=False)


if __name__ == '__main__':
    log.info("Start script")
    filename = "previous.csv"

    df_new = create_new_items()
    df_old = load_old_items(filename)
    process_dfs(df_new, df_old)
