#!/usr/bin/env python
# coding: utf-8

import requests
import asyncio
import json
import time
import aiohttp
from bs4 import BeautifulSoup
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
    header = {"Connection": "keep-alive", "User-Agent": ua}
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
                x_pn = row.product_name.split(",")[0].strip()
                y_pn = row.product_name.split(",")[1].strip()
                pn = {x_pn: y_pn}
            except:
                pn = None

    for row in settings_df.itertuples(index=True):
        if row.sitecode == sitecode:
            try:
                x_c = row.code.split(",")[0].strip()
                y_c = row.code.split(",")[1].strip()
                c = {x_c: y_c}
            except:
                c = None

    for row in settings_df.itertuples(index=True):
        if row.sitecode == sitecode:
            try:
                x_pr = row.price.split(",")[0].strip()
                y_pr = row.price.split(",")[1].strip()
                pr = {x_pr: y_pr}
            except:
                pr = None

    for row in settings_df.itertuples(index=True):
        if row.sitecode == sitecode:
            try:
                x_st = row.stock.split(",")[0].strip()
                y_st = row.stock.split(",")[1].strip()
                st = {x_st: y_st}
            except:
                st = None
    return pn, c, pr, st


urls_df, urls_list, useragents_list, settings_df = auth_sheet_and_get_settings()


product_list = pd.DataFrame()


async def save_rows(sitecode, product_name, code, price, stock, date, url):
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


async def scrape(url, header):
    async with aiohttp.ClientSession(headers=get_random_header()) as session:
        try:
            async with session.get(url) as response:
                # print("Status", response.status)
                for row in urls_df.itertuples():
                    if row.url == url:
                        sitecode = row.sitecode
                        date = time_now()
                        pn, c, pr, st = get_tags(settings_df, sitecode)
                        if response.status == 200:
                            body = await response.text()
                            soup = BeautifulSoup(body, "html.parser")

                            product_name = soup.find(**pn).text.strip()

                            try:
                                if sitecode == 2:
                                    code = soup.find(**c).split("/")[-1].text.strip()
                                else:
                                    code = soup.find(**c).text.strip()
                            except:
                                code = ""
                                print("Code missing", code, url)

                            try:
                                price_init = soup.find(**pr)

                                if any(sitecode == item for item in [1]):
                                    price = price_init.next_element.replace(
                                        ".", ""
                                    ).strip()
                                    price = float(price)
                                elif any(sitecode == item for item in [3]):
                                    price = price_init.next_element.text.strip()[:-6]
                                    price = float(price)
                                else:
                                    price = (
                                        price_init.text.strip()[:-4]
                                        .replace(".", "")
                                        .replace(",", ".")
                                        .strip()
                                    )
                                    price = float(price)
                            except:
                                price = 0.000001
                                price = float(price)
                                print("Price missing", price_init, url)

                            try:
                                stock = soup.find(**st).text.strip()
                            except:
                                stock = ""
                                print("Stock missing", stock, url)

                        else:
                            pass
                            product_name, code, price, stock = None
                            print(
                                "Request failed with status code:", response.status, url
                            )

                        await save_rows(
                            sitecode, product_name, code, price, stock, date, url
                        )
        except Exception as e:
            print(e, url)


async def main():
    start_time = time.time()

    tasks = []
    for url in urls_list:
        task = asyncio.create_task(scrape(url, get_random_header()))
        tasks.append(task)

    print("Saving the output of extracted information")
    await asyncio.gather(*tasks)

    time_difference = time.time() - start_time
    print(f"Scraping time: %.2f seconds." % time_difference)


loop = asyncio.get_event_loop()
loop.run_until_complete(main())


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
    sheet.values_append("raw", {"valueInputOption": "RAW"}, {"values": df_values})
    print("Values appended to sheet")


def get_raw_df():
    raw_sheet = sheet.worksheet("raw")
    raw_get = raw_sheet.get_all_values()
    raw_df = pd.DataFrame(
        raw_get,
        columns=["Sitecode", "Product name", "Code", "Price", "Stock", "Date", "URL"],
    )
    raw_df = raw_df[1:]
    raw_df.reset_index(drop=True, inplace=True)

    raw_df = format_df(raw_df)
    raw_df["Date"] = pd.to_datetime(raw_df["Date"])
    return raw_df


def get_current_previous(raw_df):
    previous_df = raw_df.groupby(["Sitecode", "Code", "URL"], as_index=False)[
        "Date"
    ].apply(lambda x: x.sort_values(ascending=False).nlargest(2).min())
    previous_df.reset_index()

    now_df = raw_df.groupby(["Sitecode", "Code", "URL"], as_index=False)["Date"].apply(
        lambda x: x.sort_values(ascending=False).nlargest(1).min()
    )
    now_df.reset_index()

    previous_df = previous_df.merge(raw_df, on=["Sitecode", "Code", "URL", "Date"])
    now_df = now_df.merge(raw_df, on=["Sitecode", "Code", "URL", "Date"])
    return now_df, previous_df


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


send_df_to_sheets(product_list)  ## send current scraped data to sheets

th_sheet = sheet.worksheet("thresholds")
THRESHOLD = float(th_sheet.acell("A2").value)

th_sheet = sheet.worksheet("thresholds")
THRESHOLD = float(th_sheet.acell("A2").value)


def process_alerts():
    raw_df = get_raw_df()  ## read all data
    now_df, previous_df = get_current_previous(
        raw_df
    )  ## grab current and previous data to compare
    for prev in previous_df.itertuples():
        for now in now_df.itertuples():
            if (
                now.Code == prev.Code
                and now.Sitecode == prev.Sitecode
                and now.URL == prev.URL
            ):
                diff = int(now.Price - prev.Price)
                diffpc = float(now.Price / prev.Price - 1)
                diffpc_str = str(round(diffpc * 100, 2)) + str("%")
                if abs(diffpc) >= THRESHOLD:
                    print(f"Difference higher than {THRESHOLD*100}% found.")
                    if diff > 0:
                        alert_message = f"[{diff}] [{now.Stock}] Price increased to {now.Price} from {prev.Price}, difference of {diffpc_str} {now.URL}"
                        print(alert_message)
                        send_to_telegram(alert_message)
                    elif diff < 0:
                        alert_message = f"[{diff}] [{now.Stock}] Price decreased to {now.Price} from {prev.Price}, difference of {diffpc_str} {now.URL}"
                        print(alert_message)
                        send_to_telegram(alert_message)
                    else:
                        alert_message = None
                        print(alert_message)
    print("Finished.")


if __name__ == "__main__":
    process_alerts()
