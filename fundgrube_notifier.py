import json
import logging as log
import os
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from typing import Tuple

import pandas as pd
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter, Retry

load_dotenv()
dev = os.getenv("ENV") == 'dev'
if dev:
    log.basicConfig(level=log.DEBUG, format='%(asctime)s.%(msecs)04d %(levelname)s: %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S', encoding="utf-8")
else:
    log.basicConfig(level=log.INFO, format='%(asctime)s %(levelname)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S',
                    encoding="utf-8")

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
    filename_html = f"data/{retailer['name']}.html"

    if dev and os.path.isfile(filename_html):
        last_update = os.path.getmtime(filename_html)
        time_diff = datetime.now().timestamp() - last_update
        if time_diff < 50 * 60:
            with open(filename_html, "r", encoding="utf-8") as file:
                log.debug("Loaded items from file")
                return file.read()
    html = requests.get(retailer["url"]).content
    if dev:
        with open(filename_html, "wb") as file:
            file.write(html)
    return html.decode("utf-8")


def create_new_items() -> pd.DataFrame:
    with open("data/products.json", "r", encoding="utf-8") as search_file:
        products = json.load(search_file)
    df = pd.DataFrame({})

    for retailer in retailers:
        log.info(f"Request {retailer['name']} data")
        html = request(retailer)
        log.debug("Create soup")
        soup = BeautifulSoup(html, 'html.parser')
        log.debug("Parse soup")
        body = soup.body

        # check for last update
        last_update_str = body.select_one('div:first-child').text
        last_update = datetime.strptime(last_update_str, '\n\nLetzter Abruf: %d.%m.%Y, %H:%M Uhr')
        log.debug(f"Last update: {last_update}")

        if datetime.now() - last_update > timedelta(hours=2, minutes=30):
            message = f"No updated data available. Last update: {last_update}. Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}."
            log.error(message)
            raise ValueError(message)

        for product in products:
            terms_include = [x.lower() for x in product.get("include")]
            tags = body.find_all('a', text=lambda text: text and all([term in text.lower() for term in terms_include]))
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
                if "exclude" in product:
                    terms_exclude = [x.lower() for x in product.get("exclude")]
                    df_tmp = df_tmp[~df_tmp["name"].str.contains("|".join(terms_exclude), case=False, regex=True)]
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
        log.info("\n" + df[:new_count].drop(columns="time").to_string(index=False, header=False))

    log.debug("Save results")
    df.to_csv(filename, encoding="utf-8", index=False)
    return new_count, df


def notify(new_count: int, df_merge: pd.DataFrame, error: Exception = None) -> None:
    mail_sender = os.getenv("MAIL_SENDER")
    mail_password = os.getenv("MAIL_PASSWORD")
    if (mail_sender and mail_password and new_count > 0) or error:
        smtp_server = os.getenv("SMTP_SERVER", 'smtp.gmail.com')
        smtp_port = os.getenv("SMTP_PORT", 587)
        sender = f'Fundgrube Notifier <{mail_sender}>'
        receiver = os.getenv("MAIL_RECEIVER", mail_sender)

        if error:
            message_text = str(error)
        else:
            df_new_items = df_merge[:new_count].drop(columns="time")
            message_text = "\n".join(["  ".join(list(row[1])) for row in df_new_items.iterrows()])
        log.debug(f"Mail message:\n{message_text}")
        message = MIMEText(message_text, "plain", "utf-8")

        if error:
            message['Subject'] = f"An error occured"
        else:
            message['Subject'] = f"{new_count} new items"
        if mail_sender == receiver:
            message['Subject'] = "Fundgrube: " + message['Subject']
        message['From'] = sender
        message['To'] = receiver

        smtp_client = smtplib.SMTP(smtp_server, smtp_port)
        smtp_client.starttls()
        smtp_client.login(mail_sender, mail_password)
        smtp_client.sendmail(sender, [receiver], message.as_string())
        smtp_client.quit()


if __name__ == '__main__':
    log.debug("Start script")
    filename = "data/results.csv"

    try:
        df_new = create_new_items()
        df_old = load_old_items(filename)
        new_count, df_merge = process_dfs(df_new, df_old)
    except Exception as e:
        notify(0, pd.DataFrame({}), e)
    else:
        notify(new_count, df_merge)
