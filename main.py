import os.path

import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import json
# TODO better logging
# TODO code formatting, sorting imports, ...


def request(url):
    response = requests.get(url)
    # print(response.status_code)
    # print(response.content)
    # TODO error handling
    # with open("response3.html", "wb") as file:
    #     file.write(response.content)
    return response.content


def save_csv(df, filename):
    df.to_csv(filename, encoding="utf8", index=False)


if __name__ == '__main__':
    print("Start script")
    chains = [{
        "name": "Saturn",
        "url": "https://schneinet.de/saturn.html"
    },
    {
        "name": "MM",
        "url": "https://schneinet.de/mediamarkt.html"
    }]
    with open("terms.json", "r", encoding="utf8") as search_file:
        terms = json.load(search_file)
    df_new = pd.DataFrame({})
    filename = "previous.csv"

    for chain in chains:
        print(f"Request {chain['name']} data")
        html = request(chain["url"])
        # with open("response2.html", "r", encoding="utf8") as html:
        print("Create soup")
        soup = BeautifulSoup(html, 'html.parser')
        print("Parse soup")
        body = soup.body

        for term_obj in terms:
            tags = body.find_all('a', text=lambda text: text and all([term in text.lower() for term in term_obj["terms"]]))
            chains = [tag.find_parent("div").previous_sibling.contents[0].text.strip() for tag in tags]
            images = [tag.get("href") for tag in tags]
            names = [tag.text for tag in tags]
            prices = [tag.parent.previous_sibling.contents[0].text for tag in tags]
            df_tmp = pd.DataFrame({"name": names, "price": prices, "store": chains, "image": images})
            df_new = pd.concat([df_new, df_tmp])

    print("Load previous results")
    if os.path.isfile(filename):
        df_old = pd.read_csv(filename, header=0, encoding="utf8", dtype={"name": "object", "price": "object", "store": "object", "image": "object"})
    else:
        df_old = pd.DataFrame({"name": [], "price": [], "store": [], "image": [], "time": []})

    print("Merge results")
    df = pd.merge(left=df_new, right=df_old, how="left", on=["name", "price", "store", "image"])
    new_count = df["time"].isna().sum()
    df["time"] = df["time"].fillna(datetime.now())
    print(f"There were {new_count} new results!")
    # TODO better notifications
    df.sort_values(by=["time"])

    print("Save results")
    save_csv(df, filename)
