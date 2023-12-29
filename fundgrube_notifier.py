import json
import logging as log
import os
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from pathlib import Path
from typing import Tuple

import pandas as pd
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter, Retry

load_dotenv()
dev = os.getenv("ENV") == 'dev'

retailers = [
    {
        "name": "Saturn",
        "url": "https://schneinet.de/saturn.html"
    },
    {
        "name": "MM",
        "url": "https://schneinet.de/mediamarkt.html"
    }]


class NoDataException(Exception):
    """Exception thrown, if there is no up-to-date data available"""


def configure_logging() -> None:
    """Configure logging, so the output of the current run is logged to the terminal and a file."""
    date_format = '%Y-%m-%d %H:%M:%S'
    debug_format = log.Formatter('%(asctime)s.%(msecs)04d %(levelname)s: %(message)s', datefmt=date_format)
    prod_format = log.Formatter('%(asctime)s %(message)s', datefmt=date_format)
    file_handler = log.FileHandler("run.log", mode="w+")
    file_handler.setLevel(log.DEBUG)
    file_handler.setFormatter(debug_format)
    stream_handler = log.StreamHandler()
    if dev:
        stream_handler.setLevel(log.DEBUG)
        stream_handler.setFormatter(debug_format)
    else:
        stream_handler.setLevel(log.INFO)
        stream_handler.setFormatter(prod_format)
    log.basicConfig(level=log.DEBUG,
                    handlers=[file_handler, stream_handler],
                    encoding="utf-8")


def configure_session() -> None:
    """Configure the session, so network calls are retried."""
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=1, status_forcelist=[502, 503, 504])
    adapter = HTTPAdapter(max_retries=retries)
    session.mount('http://', adapter)
    session.mount('https://', adapter)


def request(retailer: retailers) -> str:
    """Request the current data for a given retailer.

    Args:
        retailer: The retailer to request data from.

    Returns:
        All current articles in html format.
    """
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
    """Request current data and extract articles matching the filters defined in `products.json`.

    Returns:
        DataFrame with the extracted articles.

    Raises:
        ValueError: If the data source has not been updated for 2.5 hours.
    """
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
            raise NoDataException()

        for product in products:
            terms_include: list[str | list[str]] = [term_or_list.lower() if isinstance(term_or_list, str)
                                                    else [term.lower() for term in term_or_list]
                                                    for term_or_list in product.get("include")]
            tags = body.find_all('a', string=lambda text: text and all(
                term_or_list in text.lower() if isinstance(term_or_list, str)
                else any(term in text.lower() for term in term_or_list)
                for term_or_list in terms_include))
            stores = [tag.find_parent("div").previous_sibling.contents[0].text.strip() for tag in tags]
            images = [tag.get("href") for tag in tags]
            names = [tag.text for tag in tags]
            prices = [tag.parent.previous_sibling.contents[0].text for tag in tags]
            df_tmp = pd.DataFrame({"name": names, "price": prices, "store": stores, "image": images})
            if df_tmp.size > 0:
                df_tmp["store"] = retailer.get("name") + " - " + df_tmp["store"]
                if "price" in product:
                    df_tmp = df_tmp[
                        pd.to_numeric(df_tmp["price"].str.slice(stop=-1).str.replace(",", "")) <= product.get(
                            "price") * 100]
                if "exclude" in product:
                    terms_exclude = [x.lower() for x in product.get("exclude")]
                    df_tmp = df_tmp[~df_tmp["name"].str.contains("|".join(terms_exclude), case=False, regex=True)]
                if "store" in product:
                    df_tmp = df_tmp[
                        df_tmp["store"].str.contains("|".join(product.get("store")), case=False, regex=True)]
                df = pd.concat([df, df_tmp])
            df = df.drop_duplicates()
    return df


def check_tag(text: str, terms_include: list[str | list[str]]):
    # find matching tags/products (all terms_include must be included. For lists only one term has to match)
    return text and all(term_or_list in text.lower() if isinstance(term_or_list, str)
                        else any(term in text.lower() for term in term_or_list)
                        for term_or_list in terms_include)


def load_old_items(results_filename: str) -> pd.DataFrame:
    """Load articles retrieved in the previous run from a specified file.

    Args:
        results_filename: The name of the file with the articles.

    Returns:
        DataFrame with the articles form the previous run.
    """
    log.debug("Load previous results")
    if os.path.isfile(results_filename):
        return pd.read_csv(results_filename, header=0, encoding="utf-8",
                           dtype={"name": "object", "price": "object", "store": "object",
                                  "image": "object"}, parse_dates=["time"])
    else:
        return pd.DataFrame({"name": [], "price": [], "store": [], "image": [], "time": []})


def combine_dfs(df_current: pd.DataFrame, df_previous: pd.DataFrame, results_filename: str) -> Tuple[int, pd.DataFrame]:
    """Combine articles from the previous and current run to determine the new articles.

    Args:
        df_current: DataFrame with the articles from the current run.
        df_previous: DataFrame with the articles from the previous run.
        results_filename: Name of the file to store the results for the next run.

    Returns:
        Number of new articles.
        DataFrame with articles from the current run, ordered by timestamps.
    """
    df = pd.merge(left=df_current, right=df_previous, how="left", on=["name", "price", "store", "image"])
    df = df.drop_duplicates()
    new_count = df["time"].isna().sum()

    df["time"] = df["time"].fillna(datetime.now())
    df = df.sort_values(by=["time", "store", "name"], ascending=False)
    log.info(f"There were {new_count} new results")
    if new_count > 0:
        log.info("\n" + df[:new_count].drop(columns="time").to_string(index=False, header=False))

    log.debug("Save results")
    df.to_csv(results_filename, encoding="utf-8", index=False)
    return new_count, df


def mail_notify(new_count: int, df_merge: pd.DataFrame, error: Exception = None) -> None:
    """Notify the user about new articles via email, if set up.

    Args:
        new_count: Number of new articles.
        df_merge: DataFrame with articles from the current run, ordered by timestamps.
        error: The error to notify the user about, should one have occurred.
    """
    mail_sender = os.getenv("MAIL_SENDER")
    mail_password = os.getenv("MAIL_PASSWORD")
    previous_error_file = Path("data/previous_error.txt")
    if previous_error_file.exists():
        with open(previous_error_file, "r") as file:
            old_error = file.read()
    else:
        old_error = None
    if mail_sender and mail_password and (new_count > 0 or error.__class__.__name__ != old_error):
        # only send mail if: new data, or error, or error fixed
        smtp_server = os.getenv("SMTP_SERVER", 'smtp.gmail.com')
        smtp_port = os.getenv("SMTP_PORT", 587)
        sender = f'Fundgrube Notifier <{mail_sender}>'
        receiver = os.getenv("MAIL_RECEIVER", mail_sender)

        if error:
            message_text = str(error)
            subject = f"An error occured"
            with open(previous_error_file, "w") as file:
                file.write(error.__class__.__name__)
        elif new_count > 0:
            df_new_items = df_merge[:new_count].drop(columns="time")
            message_text = " \n".join(["  ".join(list(row[1])) for row in df_new_items.iterrows()])
            subject = f"{new_count} new items"
        else:
            message_text = str("Previous error fixed")
            subject = f"Error fixed"
            os.remove(previous_error_file)
        log.debug(f"Mail message:\n{message_text}")
        message = MIMEText(message_text, "plain", "utf-8")

        if mail_sender == receiver:
            message['Subject'] = "Fundgrube: " + subject
        else:
            message['Subject'] = subject
        message['From'] = sender
        message['To'] = receiver

        smtp_client = smtplib.SMTP(smtp_server, smtp_port)
        smtp_client.starttls()
        smtp_client.login(mail_sender, mail_password)
        smtp_client.sendmail(sender, [receiver], message.as_string())
        smtp_client.quit()


def main() -> None:
    """Main function which executes all steps of the script."""
    configure_logging()
    configure_session()
    log.debug("Start script")
    results_filename = "data/results.csv"

    try:
        df_new = create_new_items()
        df_old = load_old_items(results_filename)
        new_count, df_merge = combine_dfs(df_new, df_old, results_filename)
    except Exception as e:
        mail_notify(0, pd.DataFrame({}), e)
    else:
        mail_notify(new_count, df_merge)


if __name__ == '__main__':
    main()
