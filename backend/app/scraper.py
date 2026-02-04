import json
import re
import asyncio
from datetime import date, timedelta
from typing import List, Dict, Optional
from playwright.async_api import async_playwright, Page, Route

from app.settings import settings
from app.redis_client import redis_client

# --- CONFIGURAZIONE ---
BASE_URL = "https://intragenzia.adisu.umbria.it"
LOGIN_URL = f"{BASE_URL}/user/login"
MENU_TODAY = f"{BASE_URL}/menu-odierni"
MENU_TOMORROW = f"{BASE_URL}/menu-domani"

CATEGORY_MAP = {
    "Primi piatti": "primi_piatti",
    "Secondi piatti": "secondi_piatti",
    "Contorni": "contorni",
    "Frutta": "frutta",
    "Dessert": "dessert",
}

NUMERIC_ID = re.compile(r"^\d+$")

# --- UTILITY PER PERFORMANCE ---
async def block_resources(route: Route):
    """Blocca immagini, font e CSS per velocizzare il caricamento."""
    if route.request.resource_type in ["image", "media", "font", "stylesheet"]:
        await route.abort()
    else:
        await route.continue_()

async def setup_optimized_page(page: Page):
    """Applica il blocco risorse a una pagina."""
    await page.route("**/*", block_resources)


# --- FUNZIONI DI BASE ---

async def login(page: Page):
    """Esegue il login al portale ADISU."""
    print(f"Eseguendo il login per {settings.MENU_USERNAME}...")
    await page.goto(LOGIN_URL)
    
    await page.wait_for_selector('input[name="name"]')
    await page.fill('input[name="name"]', settings.MENU_USERNAME)
    await page.fill('input[name="pass"]', settings.MENU_PASSWORD)
    await page.click('input[id="edit-submit"], button:has-text("Log in"), input[value="Log in"]')
    await page.wait_for_load_state("networkidle")
    print("Login effettuato.")


async def get_menu_urls(page: Page) -> List[Optional[str]]:
    urls = [None, None, None, None] 
    pages_to_check = [(MENU_TODAY, 0), (MENU_TOMORROW, 2)]
    
    for page_url, start_idx in pages_to_check:
        print(f"Cercando link menu in: {page_url}")
        await page.goto(page_url)
        
        links = page.locator("div.view-menu a")
        count = await links.count()
        
        for i in range(count):
            link = links.nth(i)
            text = await link.text_content()
            href = await link.get_attribute("href")
            
            if not text or not href:
                continue

            if "Mensa Pascoli" in text:
                full_url = href if href.startswith("http") else f"{BASE_URL}{href}"
                text_lower = text.lower()
                if "pranzo" in text_lower:
                    urls[start_idx] = full_url
                elif "cena" in text_lower:
                    urls[start_idx + 1] = full_url
                    
    return urls


async def parse_menu_page(page: Page, url: str) -> tuple[Dict, bool, bool]:
    print(f"Parsing menu: {url}")
    await page.goto(url)
    
    prenotabile = False
    checkbox_wrapper = page.locator(".js-form-item-vuoi-prenotare")
    
    if await checkbox_wrapper.count() > 0:
        classes = await checkbox_wrapper.get_attribute("class") or ""
        if "js-webform-states-hidden" in classes:
            prenotabile = False
        else:
            prenotabile = True
    else:
        prenotabile = False

    prenotato = False
    warning_loc = page.locator(".alert.alert-warning")
    if await warning_loc.count() > 0:
        msg = await warning_loc.text_content()
        if msg and "Risulta già presente una prenotazione" in msg:
            prenotato = True
            prenotabile = False 

    grouped = {v: [] for v in CATEGORY_MAP.values()}
    fieldsets = page.locator("fieldset")
    fs_count = await fieldsets.count()
    
    for i in range(fs_count):
        fs = fieldsets.nth(i)
        legend_loc = fs.locator(".fieldset-legend")
        if await legend_loc.count() == 0: continue
            
        legend_text = (await legend_loc.text_content()).strip()
        cat_key = CATEGORY_MAP.get(legend_text)
        if not cat_key: continue
            
        radios = fs.locator("input[type=radio]")
        r_count = await radios.count()
        
        for j in range(r_count):
            radio = radios.nth(j)
            val = await radio.get_attribute("value")
            if not val or not NUMERIC_ID.match(val.strip()): continue
                
            radio_id = await radio.get_attribute("id")
            label_loc = fs.locator(f"label[for='{radio_id}']")
            if await label_loc.count() > 0:
                name = (await label_loc.text_content()).strip()
                grouped[cat_key].append({"id": val.strip(), "nome": name})
                
    return grouped, prenotato, prenotabile


async def book_meal(page: Page, meal_url: str, dish_ids: List[str]) -> bool:
    """Prenotazione robusta con JS, AJAX handling e attesa selettiva."""
    print(f"Inizio prenotazione su: {meal_url}")
    await page.goto(meal_url)
    await page.wait_for_load_state("networkidle")
    
    # 1. Start
    try:
        await page.wait_for_selector("#edit-vuoi-prenotare", state="attached")
        check_script = """() => {
            var el = document.querySelector('#edit-vuoi-prenotare');
            if (el && !el.checked) { el.click(); return true; }
            return false;
        }"""
        if await page.evaluate(check_script):
            print("Checkbox 'Vuoi prenotare' cliccato (via JS).")
    except Exception as e:
        print(f"Errore Checkbox Start: {e}")
        return False

    # Procedi 1
    try:
        await page.wait_for_selector("#edit-cards-next", state="attached")
        await page.evaluate("() => document.querySelector('#edit-cards-next').click()")
    except Exception as e:
        print(f"Errore bottone Procedi 1: {e}")
        return False
    
    # 2. Tipo Menu
    await page.wait_for_selector("#edit-tipologia-menu-standard", state="attached")
    await page.evaluate("() => document.querySelector('#edit-tipologia-menu-standard').click()")
    
    # Procedi 2
    await page.wait_for_selector("#edit-cards-next", state="attached")
    await page.evaluate("() => document.querySelector('#edit-cards-next').click()")
    
    # 3. Selezione Piatti
    try:
        await page.wait_for_selector("fieldset", state="attached")
        await asyncio.sleep(0.5) 
    except: pass

    print(f"Seleziono i piatti: {dish_ids}")
    for dish_id in dish_ids:
        js_script = f"""() => {{
            var el = document.querySelector('input[type="radio"][value="{dish_id}"]');
            if (el) {{ el.scrollIntoView(); el.click(); return true; }}
            else {{ return false; }}
        }}"""
        if await page.evaluate(js_script):
            print(f" - Selezionato piatto ID: {dish_id}")
        else:
            print(f" - ATTENZIONE: Piatto ID {dish_id} non trovato!")

    # 4. Anteprima
    print("Clicco su Anteprima...")
    await page.wait_for_selector("#edit-actions-preview-next", state="attached")
    await page.evaluate("() => document.querySelector('#edit-actions-preview-next').click()")
    
    # 5. Conferma (AJAX)
    print("Attendo caricamento AJAX del bottone finale...")
    try:
        submit_selector = 'input[value="Invia"]'
        await page.wait_for_selector(submit_selector, state="attached", timeout=15000)
        # Piccolo sleep per stabilità JS
        await asyncio.sleep(1)

        submit_script = """() => {
            var btn = document.querySelector('input[value="Invia"]');
            if (btn) { btn.click(); return true; }
            return false;
        }"""
        
        # CLICCATO!
        if await page.evaluate(submit_script):
            print("Prenotazione INVIATA (Click finale).")
            
            # ATTESA DI SICUREZZA:
            # Aspettiamo che la rete si calmi
            await page.wait_for_load_state("networkidle")
            # E aggiungiamo 3 secondi brutali ma sicuri per essere certi che Drupal abbia finito
            await asyncio.sleep(3)
            
            return True
        else:
            print("Errore: Impossibile cliccare il pulsante 'Invia'.")
            return False
            
    except Exception as e:
        print(f"Errore bottone Invia: {e}")
        return False


async def scrape_and_cache_daily():
    print("--- INIZIO SCRAPING GIORNALIERO ---")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # Usiamo user agent reale
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        # OTTIMIZZAZIONE: Blocchiamo le risorse anche qui
        await setup_optimized_page(page)
        
        try:
            await login(page)
            menu_urls = await get_menu_urls(page)
            
            today = date.today()
            tomorrow = today + timedelta(days=1)
            
            meal_definitions = [
                (today, "pranzo"), (today, "cena"),
                (tomorrow, "pranzo"), (tomorrow, "cena")
            ]
            
            results = {today.isoformat(): [], tomorrow.isoformat(): []}
            
            for i, url in enumerate(menu_urls):
                day_obj, tipo = meal_definitions[i]
                if not url: continue
                
                dishes, prenotato, prenotabile = await parse_menu_page(page, url)
                
                meal_data = {
                    "data": day_obj.isoformat(),
                    "tipo_pasto": tipo,
                    "prenotato": prenotato,
                    "prenotabile": prenotabile,
                    "piatti": dishes
                }
                results[day_obj.isoformat()].append(meal_data)
            
            for day_str, meals in results.items():
                if meals:
                    key = f"menu:{day_str}"
                    await redis_client.set(key, json.dumps(meals))
                    print(f"Salvato menu per {day_str} ({len(meals)} pasti).")
                else:
                    print(f"Nessun dato per {day_str}.")

        except Exception as e:
            print(f"ERRORE CRITICO SCRAPING: {e}")
        finally:
            await browser.close()
            print("--- FINE SCRAPING GIORNALIERO ---")

async def get_cached_menu(day: date):
    key = f"menu:{day.isoformat()}"
    raw = await redis_client.get(key)
    if not raw: return None
    return json.loads(raw)
