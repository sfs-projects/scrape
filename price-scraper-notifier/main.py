#!/usr/bin/env python
# coding: utf-8

import requests
import asyncio
import time
import aiohttp
from bs4 import BeautifulSoup
import re
import gspread
import pandas as pd
from datetime import datetime
import random
import os
import ast
from oauth2client.service_account import ServiceAccountCredentials


API_TOKEN = os.getenv("API_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
SHEET_ID = os.getenv("SHEET_ID")
GOOGLE_CREDS = os.getenv("GOOGLE_CREDS")
GOOGLE_CREDS = ast.literal_eval(GOOGLE_CREDS.replace("\n", "\\n"))


def auth_sheet_and_get_settings():
    scope = ["https://www.googleapis.com/auth/spreadsheets"]
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(GOOGLE_CREDS, scope)
    client = gspread.authorize(credentials)
    global sheet
    sheet = client.open_by_key(SHEET_ID)

    urls_sheet = sheet.worksheet("urls")
    urls_get = urls_sheet.get_all_values()
    urls_df = pd.DataFrame(urls_get, columns=["sitecode", "url"])
    urls_df = urls_df[1:]
    urls_df["sitecode"] = pd.to_numeric(urls_df["sitecode"], errors="ignore")
    urls_df.reset_index(drop=True, inplace=True)

    urls_list = urls_df["url"].tolist()
    urls_list = list(set(urls_list))
    urls_list = list(filter(None, urls_list))

    useragents_sheet = sheet.worksheet("uas")
    useragents_list = useragents_sheet.col_values(1)
    useragents_list = list(filter(None, useragents_list))

    settings_sheet = sheet.worksheet("settings")
    settings_get = settings_sheet.get_all_values()
    settings_df = pd.DataFrame(
        settings_get,
        columns=["sitecode", "site", "product_name", "code", "price", "stock"],
    )
    settings_df = settings_df[1:]
    settings_df["sitecode"] = pd.to_numeric(settings_df["sitecode"], errors="ignore")
    settings_df.reset_index(drop=True, inplace=True)

    return urls_df, urls_list, useragents_list, settings_df


def get_random_header():
    ua = random.choice(useragents_list)
    header = {
        "Connection": "close",
        "User-Agent": ua,
        "Content-Type": "application/json",
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate",
    }
    return header


def time_now():
    # datetime object containing current date and time
    now = datetime.now()
    # dd/mm/YY H:M:S
    dt_string = now.strftime("%d/%m/%Y %H:%M:%S")
    return dt_string


def get_tags(settings_df, sitecode):
    for row in settings_df.itertuples(index=True):
        if row.sitecode == sitecode:
            try:
                pn_string = row.product_name.strip()
                c_string = row.code.strip()
                pr_string = row.price.strip()
                st_string = row.stock.strip()
            except:
                pn_string, c_string, pr_string, st_string = None

    return pn_string, c_string, pr_string, st_string


urls_df, urls_list, useragents_list, settings_df = auth_sheet_and_get_settings()


product_list = pd.DataFrame()
timeout = 25


async def save_items(sitecode, product_name, code, price, stock, date, url):
    global product_list
    items = {
        "Sitecode": sitecode,
        "Product name": product_name,
        "Code": code,
        "Price": price,
        "Stock": stock,
        "Date": date,
        "URL": url,
    }
    items_df = pd.DataFrame([items])
    product_list = pd.concat([product_list, items_df], ignore_index=True)
    product_list = product_list[product_list["Price"] != 0.000001]
    product_list.reset_index(drop=True, inplace=True)


async def scrape(url):
    header = get_random_header()
    async with aiohttp.ClientSession(headers=header) as session:
        await asyncio.sleep(1)
        try:
            async with session.get(url, timeout=timeout) as response:
                for row in urls_df.itertuples():
                    if row.url == url:
                        sitecode = row.sitecode
                        date = time_now()
                        pn_string, c_string, pr_string, st_string = get_tags(
                            settings_df, sitecode
                        )
                        if response.status == 200:
                            body = await response.text()
                            soup = BeautifulSoup(body, "lxml")

                            try:
                                if sitecode == 4:
                                    product_name = soup.find(
                                        class_=re.compile(pn_string)
                                    ).text.strip()
                                else:
                                    product_name = soup.find(
                                        class_=re.compile(pn_string)
                                    ).next_element.text.strip()
                            except Exception as e:
                                product_name = ""
                                print("Product name missing", product_name, url, e)

                            try:
                                if any(sitecode == item for item in [0, 2]):
                                    code = soup.find(
                                        class_=re.compile(c_string)
                                    ).text.strip()
                                elif any(sitecode == item for item in [3, 4]):
                                    code = (
                                        soup.find(class_=re.compile(c_string))
                                        .find("span")
                                        .next_element.text.strip()
                                    )
                                else:
                                    code = soup.find(
                                        class_=re.compile(c_string)
                                    ).next_element.text.strip()
                            except Exception as e:
                                code = ""
                                print("Code missing", code, url, e)

                            try:
                                price_init = soup.find(class_=re.compile(pr_string))
                                price = (
                                    price_init.next_element.replace("RON", "")
                                    .replace(".", "")
                                    .replace(",", ".")
                                    .strip()
                                )
                                price = float(price)
                            except Exception as e:
                                price = 0.000001
                                price = float(price)
                                print(
                                    "Price missing",
                                    price_init,
                                    type(price_init),
                                    url,
                                    e,
                                )

                            try:
                                if any(sitecode == item for item in [0, 2]):
                                    stock = (
                                        soup.find(class_=re.compile(st_string))
                                        .text.replace("\n", "")
                                        .strip()
                                    )
                                elif any(sitecode == item for item in [3, 4]):
                                    stock = (
                                        soup.find(class_=re.compile(st_string))
                                        .find("span")
                                        .next_element.text.strip()
                                    )
                                else:
                                    stock = (
                                        soup.find(class_=re.compile(st_string))
                                        .next_element.text.replace("\n", "")
                                        .strip()
                                    )
                            except Exception as e:
                                stock = ""
                                print("Stock missing", stock, url, e)

                        else:
                            product_name, code, price, stock = None
                            print(
                                "Request failed with status code:", response.status, url
                            )

                        await save_items(
                            sitecode, product_name, code, price, stock, date, url
                        )
        except (Exception, BaseException, TimeoutError, asyncio.TimeoutError) as e:
            print(product_name, code, price, stock)
            print("Error finally:", e, url)


async def main():
    start_time = time.time()
    print("Saving the output")
    tasks = []

    for url in urls_list:
        task = asyncio.create_task(scrape(url))
        tasks.append(task)
    await asyncio.gather(*tasks)
    time_difference = time.time() - start_time
    print(f"Scraping time: %.2f seconds." % time_difference)


asyncio.run(main())


def format_df(dataframe):
    dataframe = dataframe.astype(
        {
            "Sitecode": "int",
            "Product name": "string",
            "Code": "string",
            "Price": "float64",
            "Stock": "string",
            "URL": "string",
        }
    )
    return dataframe


def send_df_to_sheets(dataframe):
    dataframe = format_df(dataframe)
    df_values = dataframe.values.tolist()
    sheet.values_append(
        "raw", {"valueInputOption": "USER_ENTERED"}, {"values": df_values}
    )
    print("Values appended to sheet")


def get_raw_df():
    raw_sheet = sheet.worksheet("raw")
    raw_get = raw_sheet.get_all_values()
    raw_df = pd.DataFrame(
        raw_get,
        columns=["Sitecode", "Product name", "Code", "Price", "Stock", "Date", "URL"],
    )
    raw_df = raw_df[1:]
    raw_df = raw_df[raw_df["Price"] != 0.000001]
    raw_df.reset_index(drop=True, inplace=True)

    raw_df = format_df(raw_df)
    raw_df["Date"] = pd.to_datetime(raw_df["Date"], format="%d/%m/%Y %H:%M:%S")
    return raw_df


def get_current_previous(raw_df, product_list):
    raw_df["Date"] = pd.to_numeric(raw_df["Date"])
    previous_df = raw_df.groupby(["Sitecode", "Code", "URL"], as_index=False)[
        "Date"
    ].apply(lambda x: x.sort_values(ascending=False).nlargest(2).min())
    previous_df.reset_index(drop=True, inplace=True)

    now_df = format_df(product_list)
    now_df.reset_index(drop=True, inplace=True)

    previous_df = previous_df.merge(raw_df, on=["Sitecode", "Code", "URL", "Date"])
    return now_df, previous_df


def get_min_df(raw_df):
    min_df = raw_df.groupby(["Sitecode", "Code", "URL"])["Price"].min()
    min_df = min_df.reset_index()
    return min_df


def send_to_telegram(message):
    if message == None:
        pass
    else:
        API_URL = f"https://api.telegram.org/bot{API_TOKEN}/sendMessage"
        try:
            response = requests.post(
                API_URL,
                json={
                    "chat_id": CHAT_ID,
                    "text": message,
                    "disable_web_page_preview": "true",
                },
            )
        except Exception as e:
            response = e


def get_checker_perc():
    len_p = len(product_list.index)
    len_c = len(urls_list)
    checker_perc = len_p / len_c
    checker_perc_str = str(round(checker_perc * 100, 2)) + str("%")
    if checker_perc <= 0.80:
        log_message = f"Possible errors. Only {checker_perc_str} of urls were checked. [{len_p}/{len_c}]"
        send_to_telegram(log_message)
    return checker_perc_str


send_df_to_sheets(product_list)  ## send current scraped data to sheets


th_sheet = sheet.worksheet("thresholds")
THRESHOLD = float(th_sheet.acell("A2").value)


def process_alerts():
    raw_df = get_raw_df()  ## read all data
    now_df, previous_df = get_current_previous(
        raw_df, product_list
    )  ## grab current and previous data to compare
    min_df = get_min_df(raw_df)
    for prev in previous_df.itertuples():
        for now in now_df.itertuples():
            if (
                now.Code == prev.Code
                and now.Sitecode == prev.Sitecode
                and now.URL == prev.URL
            ):
                for min_ in min_df.itertuples():
                    if (
                        now.Code == min_.Code
                        and now.Sitecode == min_.Sitecode
                        and now.URL == min_.URL
                    ):
                        minpr = float(min_.Price)
                        diff = int(now.Price - prev.Price)
                        diffpc = float(now.Price / prev.Price - 1)
                        diffpc_str = str(round(diffpc * 100, 2)) + str("%")
                        if abs(diffpc) >= THRESHOLD:
                            print(f"Difference higher than {THRESHOLD*100}% found.")
                            if diff > 0:
                                alert_message = f"[{diff}] [{now.Stock}] Price increased to {now.Price} from {prev.Price}, difference of {diffpc_str} {now.URL}. Minimum price {minpr}."
                                print(alert_message)
                                send_to_telegram(alert_message)
                            elif diff < 0:
                                alert_message = f"[{diff}] [{now.Stock}] Price decreased to {now.Price} from {prev.Price}, difference of {diffpc_str} {now.URL}. Minimum price {minpr}."
                                print(alert_message)
                                send_to_telegram(alert_message)
                            else:
                                alert_message = None
                                print(alert_message)
    checker_perc_str = get_checker_perc()
    print(f"Finished, checked {checker_perc_str} of urls.")


if __name__ == "__main__":
    process_alerts()
