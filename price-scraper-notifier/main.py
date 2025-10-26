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
import cloudscraper
# from dotenv import load_dotenv

# ─────────────────────────
# ① Env
# ─────────────────────────
# load_dotenv()

API_TOKEN = os.getenv("API_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
SHEET_ID = os.getenv("SHEET_ID")
GOOGLE_CREDS = os.getenv("GOOGLE_CREDS")
GOOGLE_CREDS = ast.literal_eval(GOOGLE_CREDS.replace("\n", "\\n"))

# ─────────────────────────
# ② Google Sheets auth + config
# ─────────────────────────
def auth_sheet_and_get_settings():
    scope = ["https://www.googleapis.com/auth/spreadsheets"]
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(GOOGLE_CREDS, scope)
    client = gspread.authorize(credentials)
    global sheet
    sheet = client.open_by_key(SHEET_ID)

    # URLs
    urls_sheet = sheet.worksheet("urls")
    urls_get = urls_sheet.get_all_values()
    urls_df = pd.DataFrame(urls_get, columns=["sitecode", "url"])
    urls_df = urls_df[1:]
    urls_df["sitecode"] = pd.to_numeric(urls_df["sitecode"], errors="coerce")
    urls_df.reset_index(drop=True, inplace=True)
    urls_list = list(filter(None, set(urls_df["url"].tolist())))

    # User agents
    uas_sheet = sheet.worksheet("uas")
    useragents_list = list(filter(None, uas_sheet.col_values(1)))

    # Settings
    settings_sheet = sheet.worksheet("settings")
    settings_get = settings_sheet.get_all_values()
    settings_df = pd.DataFrame(
        settings_get,
        columns=["sitecode", "site", "product_name", "code", "price", "stock"],
    )
    settings_df = settings_df[1:]
    settings_df["sitecode"] = pd.to_numeric(settings_df["sitecode"], errors="coerce")
    settings_df.reset_index(drop=True, inplace=True)

    return urls_df, urls_list, useragents_list, settings_df


def parse_selector_cell(cell_val: str):
    """
    Turn something like:
        ".product--title || .content--title || title"
    into:
        [".product--title", ".content--title", "title"]
    """
    if not cell_val:
        return []
    return [part.strip() for part in cell_val.split("||") if part.strip()]


def get_tags(settings_df, sitecode):
    """
    Return dict of selector lists for that sitecode.
    Each value is a list of fallback selectors in priority order.
    """
    row = settings_df[settings_df["sitecode"] == sitecode]
    if row.empty:
        return {"pn": [], "cd": [], "pr": [], "st": []}

    pn_list = parse_selector_cell(row["product_name"].values[0])
    cd_list = parse_selector_cell(row["code"].values[0])
    pr_list = parse_selector_cell(row["price"].values[0])
    st_list = parse_selector_cell(row["stock"].values[0])

    return {"pn": pn_list, "cd": cd_list, "pr": pr_list, "st": st_list}


def get_homepage_url(url):
    parts = url.split("/")
    return parts[0] + "//" + parts[2]


def get_random_header(url):
    ua = random.choice(useragents_list)
    referer = get_homepage_url(url)
    return {
        "Connection": "keep-alive",
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,ro;q=0.8",
        "Referer": referer,
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "no-cache",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Pragma": "no-cache",
    }


def time_now():
    return datetime.now().strftime("%d/%m/%Y %H:%M:%S")


# ─────────────────────────
# ③ Globals used by scraper
# ─────────────────────────
urls_df, urls_list, useragents_list, settings_df = auth_sheet_and_get_settings()

product_list = pd.DataFrame(
    columns=["Sitecode", "Product name", "Code", "Price", "Stock", "Date", "URL"]
)

timeout = 10
sem = asyncio.Semaphore(4)

# ─────────────────────────
# ④ Helpers: cleanup/normalization
# ─────────────────────────
def clean_price(raw_text):
    """
    Turn messy UI formats into a float:
      '5.299,00 lei' -> 5299.00
      '5,299.00'     -> 5299.00
      '€2,389.00'    -> 2389.00
      '7.599'        -> 7599.00
    If can't parse reliably: return 0.000001 (sentinel for "no price").
    """
    if not raw_text:
        return 0.000001
    try:
        txt = re.sub(r"[^\d,\.]", "", raw_text)

        if re.search(r"\.\d{2}$", txt):
            # "5,299.00" → remove commas
            txt = txt.replace(",", "")
        else:
            # "5.299,00" → "5299.00"
            txt = txt.replace(".", "").replace(",", ".")

        return float(txt)
    except Exception:
        return 0.000001


def normalize_spaces(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def clean_title_like_string(s: str) -> str:
    """
    When we fall back to <title>, e-comm titles are usually:
      "Cube Reaction Hybrid Race 800 black´n´metal | bike-discount.de"
    We just chop off common separators.
    Safe for all sites.
    """
    s = normalize_spaces(s)
    for sep in [" | ", " · ", " – ", " - "]:
        if sep in s:
            s = s.split(sep)[0]
            break
    return s.strip()


def try_css_selector(soup, selector: str) -> str:
    """
    Safe CSS selection: return text or ''.
    If selector is invalid (Tailwind class with [ ] etc.), swallow and return ''.
    """
    if not selector:
        return ""
    try:
        el = soup.select_one(selector)
    except Exception:
        return ""
    if not el:
        return ""
    return normalize_spaces(el.get_text(" ", strip=True))


def extract_first_match(soup, selector_list, allow_title_special=False) -> str:
    """
    Try each selector in selector_list, return first non-empty text.
    If allow_title_special=True and selector == "title", we read <title> from <head>
    and clean it with clean_title_like_string().
    """
    for sel in selector_list:
        if sel.lower() == "title" and allow_title_special:
            if soup.title and soup.title.string:
                return clean_title_like_string(soup.title.string)
        txt = try_css_selector(soup, sel)
        if txt:
            return txt
    return ""


async def save_items(sitecode, product_name, code, price, stock, date, url):
    global product_list

    row = {
        "Sitecode": sitecode,
        "Product name": product_name or "",
        "Code": code or "",
        "Price": price,
        "Stock": stock or "",
        "Date": date,
        "URL": url,
    }

    new_df = pd.DataFrame([row], columns=product_list.columns)
    if product_list.empty:
        product_list = new_df.copy()
    else:
        product_list = pd.concat([product_list, new_df], ignore_index=True)

# ─────────────────────────
# ⑤ Scrape logic
# ─────────────────────────
async def scrape(url):
    async with sem:
        header = get_random_header(url)

        async with aiohttp.ClientSession(headers=header) as session:
            try:
                # throttle a bit to look less like a bot
                await asyncio.sleep(random.uniform(0.3, 1.0))

                async with session.get(url, timeout=timeout) as response:
                    sitecode = urls_df.loc[urls_df["url"] == url, "sitecode"].values[0]
                    date = time_now()
                    tagmap = get_tags(settings_df, sitecode)
                    pn_list = tagmap["pn"]
                    cd_list = tagmap["cd"]
                    pr_list = tagmap["pr"]
                    st_list = tagmap["st"]

                    status = response.status
                    body = ""

                    if status == 200:
                        body = await response.text()
                    elif status == 403:
                        # fallback via cloudscraper for anti-bot / cf
                        try:
                            scraper = cloudscraper.create_scraper()
                            r = scraper.get(url, headers=header, timeout=timeout)
                            status = r.status_code
                            body = r.text
                        except Exception as ce:
                            print("Cloudscraper failed:", ce, url)
                            status = 403

                    if status == 200 and body:
                        soup = BeautifulSoup(body, "html.parser")

                        # dynamic extraction using selectors from the sheet:
                        product_name = extract_first_match(
                            soup,
                            pn_list,
                            allow_title_special=True  # allow <title> fallback if configured
                        )
                        code = extract_first_match(
                            soup,
                            cd_list,
                            allow_title_special=False
                        )
                        price_raw = extract_first_match(
                            soup,
                            pr_list,
                            allow_title_special=False
                        )
                        price = clean_price(price_raw)
                        stock = extract_first_match(
                            soup,
                            st_list,
                            allow_title_special=False
                        )

                        # basic debug
                        if not product_name:
                            print("Product name missing", url)
                        if price == 0.000001:
                            print("Price missing", url)
                        if not stock and len(st_list) > 0:
                            print("Stock missing", url)

                        # QUALITY GATE:
                        # If we didn't get a code OR we didn't get a real price,
                        # skip this row (prevents saving garbage from anti-bot fallback pages).
                        if (not code) or price == 0.000001:
                            print("Skipping incomplete/blocked page:", url, "| name candidate:", product_name)
                            return

                        # Save
                        await save_items(sitecode, product_name, code, price, stock, date, url)

                    else:
                        print("Request failed:", status, url)

            except Exception as e:
                print("Error finally:", e, url)


async def run_scrape():
    start = time.time()
    print("Starting scraping...")
    tasks = [asyncio.create_task(scrape(url)) for url in urls_list]
    await asyncio.gather(*tasks)
    print(f"Scraping time: {time.time() - start:.2f} seconds")

# ─────────────────────────
# ⑥ Sheets + alerting / history logic
# ─────────────────────────
def format_df(df):
    expected_cols = [
        "Sitecode",
        "Product name",
        "Code",
        "Price",
        "Stock",
        "Date",
        "URL",
    ]
    for col in expected_cols:
        if col not in df.columns:
            df[col] = "" if col != "Price" else 0.000001

    df["Price"] = pd.to_numeric(df["Price"], errors="coerce").fillna(0.000001)

    return df.astype(
        {
            "Sitecode": "int",
            "Product name": "string",
            "Code": "string",
            "Price": "float64",
            "Stock": "string",
            "URL": "string",
        }
    )


def send_df_to_sheets(df):
    df = format_df(df)
    values = df.values.tolist()
    sheet.values_append(
        "raw",
        {"valueInputOption": "USER_ENTERED"},
        {"values": values},
    )
    print("Values appended to sheet")


def get_raw_df():
    raw_sheet = sheet.worksheet("raw")
    raw_get = raw_sheet.get_all_values()
    raw_df = pd.DataFrame(
        raw_get,
        columns=["Sitecode", "Product name", "Code", "Price", "Stock", "Date", "URL"],
    )[1:]

    # normalize prices, drop "invalid price" rows
    raw_df["Price"] = raw_df["Price"].apply(clean_price)
    raw_df = raw_df[raw_df["Price"] != 0.000001].copy()
    raw_df.reset_index(drop=True, inplace=True)

    raw_df = format_df(raw_df)
    raw_df["Date"] = pd.to_datetime(raw_df["Date"], format="%d/%m/%Y %H:%M:%S")

    return raw_df


def get_current_previous(raw_df, current_df):
    raw_df["Date"] = pd.to_numeric(raw_df["Date"], errors="coerce")

    previous_df = (
        raw_df.groupby(["Sitecode", "Code", "URL"], as_index=False)["Date"]
        .apply(lambda x: x.sort_values(ascending=False).nlargest(2).min())
        .reset_index()
        .rename(columns={"Date": "PrevDate"})
    )

    previous_df = previous_df.merge(
        raw_df,
        left_on=["Sitecode", "Code", "URL", "PrevDate"],
        right_on=["Sitecode", "Code", "URL", "Date"],
        how="left",
    )
    previous_df.drop(columns=["PrevDate"], inplace=True, errors="ignore")

    now_df = format_df(current_df).reset_index(drop=True)
    return now_df, previous_df


def get_min_df(raw_df):
    return raw_df.groupby(["Sitecode", "Code", "URL"])["Price"].min().reset_index()


def send_to_telegram(message):
    if not message:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{API_TOKEN}/sendMessage",
            json={
                "chat_id": CHAT_ID,
                "text": message,
                "disable_web_page_preview": "true",
            },
        )
    except Exception as e:
        print("Telegram error:", e)


def get_checker_perc():
    len_p = len(product_list.index)
    len_c = len(urls_list)
    if len_c == 0:
        return "0%"
    perc = len_p / len_c
    perc_str = f"{round(perc * 100, 2)}%"
    if perc <= 0.70:
        send_to_telegram(
            f"⚠️ Only {perc_str} of URLs checked successfully [{len_p}/{len_c}]"
        )
    return perc_str


def process_alerts():
    raw_df = get_raw_df()
    now_df, prev_df = get_current_previous(raw_df, product_list)
    min_df = get_min_df(raw_df)

    for prev in prev_df.itertuples():
        for now in now_df.itertuples():
            if (now.Code, now.Sitecode, now.URL) == (prev.Code, prev.Sitecode, prev.URL):
                match_min = min_df[
                    (min_df.Code == now.Code)
                    & (min_df.Sitecode == now.Sitecode)
                    & (min_df.URL == now.URL)
                ]
                if match_min.empty:
                    continue

                minpr = float(match_min["Price"].values[0])
                diff = now.Price - prev.Price
                diffpc = (now.Price / prev.Price - 1) if prev.Price else 0

                if abs(diffpc) >= THRESHOLD:
                    direction = "increased" if diff > 0 else "decreased"
                    msg = (
                        f"[{int(diff)}] [{now.Stock}] Price {direction} to {now.Price} "
                        f"from {prev.Price}, Δ {round(diffpc*100,2)}%. "
                        f"Min {minpr}. {now.URL}"
                    )
                    print(msg)
                    send_to_telegram(msg)

    print(f"Finished, checked {get_checker_perc()} of URLs.")


# ─────────────────────────
# ⑦ Main runner
# ─────────────────────────
if __name__ == "__main__":
    asyncio.run(run_scrape())

    if product_list.empty:
        print("⚠️ No products scraped successfully — skipping sheet upload & alerts.")
    else:
        send_df_to_sheets(product_list)

        th_sheet = sheet.worksheet("thresholds")
        THRESHOLD = float(th_sheet.acell("A2").value)

        process_alerts()
