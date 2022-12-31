import json
import logging as log
import os
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from typing import Tuple

import pandas as pd
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter, Retry

load_dotenv()
log.basicConfig(level=log.DEBUG)

retailers = [
    {
        "name": "Saturn",
        "url": "https://schneinet.de/saturn.html"
    },
    {
        "name": "MM",
        "url": "https://schneinet.de/mediamarkt.html"
    }]

s = requests.Session()
retries = Retry(total=3, backoff_factor=1, status_forcelist=[502, 503, 504])
adapter = HTTPAdapter(max_retries=retries)
s.mount('http://', adapter)
s.mount('https://', adapter)


def request(retailer: retailers) -> str:
    filename_html = f"{retailer['name']}.html"

    prod = os.environ.get("ENV") == 'prod'

    if not prod and os.path.isfile(filename_html):
        last_update = os.path.getmtime(filename_html)
        time_diff = datetime.now().timestamp() - last_update
        if time_diff < 50 * 60:
            with open(filename_html, "r", encoding="utf-8") as file:
                log.debug("Loaded items from file")
                return file.read()
    html = requests.get(retailer["url"]).content
    if not prod:
        with open(filename_html, "wb") as file:
            file.write(html)
    return html.decode("utf-8")


# TODO check last request on websites
def create_new_items() -> pd.DataFrame:
    with open("products.json", "r", encoding="utf-8") as search_file:
        products = json.load(search_file)
    df = pd.DataFrame({})

    for retailer in retailers:
        log.debug(f"Request {retailer['name']} data")
        html = request(retailer)
        log.debug("Create soup")
        soup = BeautifulSoup(html, 'html.parser')
        log.debug("Parse soup")
        body = soup.body

        for product in products:
            terms = [x.lower() for x in product.get("terms")]
            tags = body.find_all('a', text=lambda text: text and all([term in text.lower() for term in terms]))
            stores = [tag.find_parent("div").previous_sibling.contents[0].text.strip() for tag in tags]
            images = [tag.get("href") for tag in tags]
            names = [tag.text for tag in tags]
            prices = [tag.parent.previous_sibling.contents[0].text for tag in tags]
            df_tmp = pd.DataFrame({"name": names, "price": prices, "store": stores, "image": images})
            if df_tmp.size > 0:
                if "price" in product:
                    df_tmp = df_tmp[
                        pd.to_numeric(df_tmp["price"].str.slice(stop=-1).str.replace(",", "")) <= product.get(
                            "price") * 100]
                if "terms_not" in product:
                    terms_not = [x.lower() for x in product.get("terms_not")]
                    df_tmp = df_tmp[~df_tmp["name"].str.contains("|".join(terms_not), case=False, regex=True)]
                df_tmp["store"] = retailer.get("name") + " - " + df_tmp["store"]
                df = pd.concat([df, df_tmp])
            df = df.drop_duplicates()
    return df


def load_old_items(filename: str) -> pd.DataFrame:
    log.debug("Load previous results")
    if os.path.isfile(filename):
        return pd.read_csv(filename, header=0, encoding="utf-8",
                           dtype={"name": "object", "price": "object", "store": "object",
                                  "image": "object"}, parse_dates=["time"])
    else:
        return pd.DataFrame({"name": [], "price": [], "store": [], "image": [], "time": []})


def process_dfs(df_new: pd.DataFrame, df_old: pd.DataFrame) -> Tuple[int, pd.DataFrame]:
    df = pd.merge(left=df_new, right=df_old, how="left", on=["name", "price", "store", "image"])
    df = df.drop_duplicates()
    new_count = df["time"].isna().sum()

    df["time"] = df["time"].fillna(datetime.now())
    df = df.sort_values(by=["time", "store", "name"], ascending=False)
    log.info(f"There were {new_count} new results")
    if new_count > 0:
        pd.set_option('display.max_rows', None)
        pd.set_option('display.max_columns', None)
        pd.set_option('display.width', None)
        pd.set_option('display.max_colwidth', None)
        log.info(df[0:new_count])

    log.debug("Save results")
    df.to_csv(filename, encoding="utf-8", index=False)
    return new_count, df


def notify(new_count: int, df_merge: pd.DataFrame) -> None:
    mail = os.getenv("MAIL")
    mail_pwd = os.getenv("MAIL_PWD")
    if mail and mail_pwd and new_count > 0:
        sender = 'Fundgrube Notifier'
        receiver = mail
        df_new_items = df_merge.iloc[:new_count].drop(columns="time")

        message_text = "\n".join(["  ".join(list(row[1])) for row in df_new_items.iterrows()])
        # row_generator = zip(*df_new_items.to_dict("list").values())
        # message_text = "\n".join(["  ".join(list(row)) for row in row_generator])
        log.debug("Mail message", message_text)
        message = MIMEText(message_text, "plain", "utf-8")

        message['Subject'] = f"Fundgrube: {new_count} new items"
        message['From'] = sender
        message['To'] = receiver

        smtp_client = smtplib.SMTP('smtp.gmail.com', 587)
        smtp_client.starttls()
        smtp_client.login(mail, mail_pwd)
        smtp_client.sendmail(sender, [receiver], message.as_string())
        smtp_client.quit()


if __name__ == '__main__':
    log.debug("Start script")
    filename = "results.csv"

    df_new = create_new_items()
    df_old = load_old_items(filename)
    new_count, df_merge = process_dfs(df_new, df_old)
    notify(new_count, df_merge)
    # TODO update README
    # TODO add tests
