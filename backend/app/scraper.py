import json
import re
import httpx
from bs4 import BeautifulSoup
from datetime import date, timedelta
from typing import List, Dict

from app.settings import settings
from app.redis_client import redis_client

BASE_URL = "https://intragenzia.adisu.umbria.it"
LOGIN_URL = f"{BASE_URL}/user/login"
MENU_TODAY = f"{BASE_URL}/menu-odierni"
MENU_TOMORROW = f"{BASE_URL}/menu-domani"


async def login(client: httpx.AsyncClient):
    resp = await client.get(LOGIN_URL)
    soup = BeautifulSoup(resp.text, "html.parser")

    form_build_id = soup.find("input", {"name": "form_build_id"})["value"]
    form_id = soup.find("input", {"name": "form_id"})["value"]

    payload = {
        "name": settings.MENU_USERNAME,
        "pass": settings.MENU_PASSWORD,
        "form_build_id": form_build_id,
        "form_id": form_id,
        "op": "Log in",
    }

    await client.post(LOGIN_URL, data=payload)


async def fetch_pascoli_nodes(client: httpx.AsyncClient):
    urls = [MENU_TODAY, MENU_TOMORROW]
    node_list = ["", "", "", ""]  # today lunch/dinner, tomorrow lunch/dinner

    for i, url in enumerate(urls):
        resp = await client.get(url)
        soup = BeautifulSoup(resp.text, "html.parser")
        anchors = soup.select("div.view-menu a")

        lunch_found = False
        dinner_found = False

        for a in anchors:
            text = a.get_text(strip=True)
            href = a.get("href", "")

            if "Mensa Pascoli" in text:
                if "pranzo" in text.lower() and not lunch_found:
                    node_list[i * 2] = href
                    lunch_found = True
                elif "cena" in text.lower() and not dinner_found:
                    node_list[i * 2 + 1] = href
                    dinner_found = True

    return node_list

CATEGORY_MAP = {
    "Primi piatti": "primi_piatti",
    "Secondi piatti": "secondi_piatti",
    "Contorni": "contorni",
    "Frutta": "frutta",
    "Dessert": "dessert",
}

NUMERIC_ID = re.compile(r"^\d+$")


def extract_dishes(html: str):
    soup = BeautifulSoup(html, "html.parser")

    # prenotazione già fatta
    warning = soup.select_one(".alert.alert-warning")
    prenotato = bool(warning and "Risulta già presente una prenotazione" in warning.get_text())

    # contenitore categorie
    grouped = {v: [] for v in CATEGORY_MAP.values()}

    for fieldset in soup.select("fieldset"):
        legend = fieldset.select_one(".fieldset-legend")
        if not legend:
            continue

        legend_text = legend.get_text(strip=True)
        key = CATEGORY_MAP.get(legend_text)
        if not key:
            continue

        for inp in fieldset.select("input[type=radio]"):
            value = (inp.get("value") or "").strip()
            if not NUMERIC_ID.match(value):
                continue  # scarta STANDARD, SPECIALE, ecc.

            label = fieldset.find("label", {"for": inp.get("id")})
            name = label.get_text(strip=True) if label else None
            if name:
                grouped[key].append({"id": value, "nome": name})

    return grouped, prenotato

async def scrape_menu_node(client: httpx.AsyncClient, node_path: str):
    url = node_path if node_path.startswith("http") else f"{BASE_URL}{node_path}"
    resp = await client.get(url)
    return extract_dishes(resp.text)


async def scrape_and_cache_daily():
    async with httpx.AsyncClient(follow_redirects=True) as client:
        await login(client)

        nodes = await fetch_pascoli_nodes(client)
        today = date.today()
        tomorrow = today + timedelta(days=1)

        meals = [
            (today, "pranzo", nodes[0]),
            (today, "cena", nodes[1]),
            (tomorrow, "pranzo", nodes[2]),
            (tomorrow, "cena", nodes[3]),
        ]

        day_data = {today.isoformat(): [], tomorrow.isoformat(): []}

        for d, meal_type, path in meals:
            if not path:
                continue
          
            dishes, prenotato = await scrape_menu_node(client, path)
            day_data[d.isoformat()].append({
              "data": d.isoformat(),
              "tipo_pasto": meal_type,
              "prenotato": prenotato,
              "piatti": dishes
            })

        for day, content in day_data.items():
            key = f"menu:{day}"
            await redis_client.set(key, json.dumps(content))


async def get_cached_menu(day: date):
    key = f"menu:{day.isoformat()}"
    raw = await redis_client.get(key)
    if not raw:
        return None
    return json.loads(raw)
